"""Integrated AEP stock-analysis Agent.

Code owns the workflow and deterministic market-data processing.
The already-running host Agent owns web research and semantic analysis.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Literal

from looma import agent, step, workflow


HERE = Path(__file__).resolve().parent


@dataclass
class NewsItem:
    published_at: str
    title: str
    source: str
    url: str
    summary: str
    impact: Literal["positive", "negative", "neutral", "mixed"]


@dataclass
class NewsResearch:
    window_start: str
    window_end: str
    search_queries: list[str]
    searched_sources: list[str]
    items: list[NewsItem]
    coverage_complete: bool
    coverage_note: str


@dataclass
class AnalysisRound:
    needs_more_research: bool
    research_queries: list[str]
    analysis_tracks: list[str]
    technical_view: str
    volume_turnover_view: str
    news_event_view: str
    risk_counterevidence: str
    short_term_bias: Literal["bullish", "neutral", "bearish", "mixed"]
    confidence: int
    conclusion: str
    watch_signals: list[str]


def run_json_script(script: str, *args: str):
    completed = subprocess.run(
        [sys.executable, script, *args],
        text=True,
        capture_output=True,
    )
    if completed.returncode != 0:
        raise RuntimeError(
            f"{Path(script).name} failed with {completed.returncode}: {completed.stderr}"
        )
    try:
        return json.loads(completed.stdout)
    except json.JSONDecodeError as exc:
        raise RuntimeError(
            f"{Path(script).name} did not return JSON: {completed.stdout!r}"
        ) from exc


def load_json(path: str):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def news_to_dict(value: NewsResearch) -> dict:
    return asdict(value)


def merge_news(base: NewsResearch, supplement: NewsResearch) -> NewsResearch:
    base_dict = news_to_dict(base)
    supplement_dict = news_to_dict(supplement)

    merged: dict[str, NewsItem] = {}
    for raw in [*base_dict["items"], *supplement_dict["items"]]:
        item = raw if isinstance(raw, NewsItem) else NewsItem(**raw)
        key = item.url or f"{item.published_at}:{item.title}"
        merged[key] = item

    return NewsResearch(
        window_start=base.window_start,
        window_end=base.window_end,
        search_queries=list(dict.fromkeys([*base.search_queries, *supplement.search_queries])),
        searched_sources=list(dict.fromkeys([*base.searched_sources, *supplement.searched_sources])),
        items=list(merged.values()),
        coverage_complete=base.coverage_complete or supplement.coverage_complete,
        coverage_note=" | ".join(
            part for part in [base.coverage_note, supplement.coverage_note] if part
        ),
    )


@workflow
def analyze_stock(
    *,
    name: str,
    symbol: str,
    workdir: str,
    as_of: str,
    news_days: int,
    market_days: int,
    max_research_rounds: int,
    market_fixture: str | None,
):
    root = Path(workdir).resolve()
    root.mkdir(parents=True, exist_ok=True)

    # Stage 1: deterministic target/date resolution.
    target = step(
        run_json_script,
        str(HERE / "resolve_stock.py"),
        "--name",
        name,
        "--symbol",
        symbol,
        "--as-of",
        as_of,
        "--news-days",
        str(news_days),
        "--market-days",
        str(market_days),
    )

    # Stage 2: deterministic structured market-data acquisition.
    market_args = [
        "--symbol",
        target["symbol"],
        "--start",
        target["market_fetch_start"],
        "--end",
        target["market_fetch_end"],
        "--market-days",
        str(target["market_days"]),
        "--output",
        str(root / "market-data.json"),
    ]
    if market_fixture:
        market_args.extend(["--fixture", market_fixture])

    market_meta = step(
        run_json_script,
        str(HERE / "fetch_market_data.py"),
        *market_args,
    )
    market = load_json(market_meta["market_file"])

    # Stage 3: deterministic K-line / volume / turnover feature engineering.
    features = step(
        run_json_script,
        str(HERE / "build_market_features.py"),
        "--market",
        market_meta["market_file"],
        "--output",
        str(root / "market-features.json"),
    )

    # Stage 4: the host performs recent-news web research.
    news = agent(
        task=(
            f"上网查询 {target['name']} ({target['symbol']}) 在 "
            f"{target['news_start']} 至 {target['news_end']} 之间发布的相关新闻。"
            "只把发布时间落在这个窗口内的新闻作为本次新闻证据，不要用更早新闻填充。"
            "使用当前宿主原生的 web/search/browser 能力；不要调用另一个 Agent CLI、SDK 或模型 API。"
            "优先公司公告、交易所、监管披露和可信财经媒体。"
            "搜索股票名称和股票代码，记录实际 search_queries，并尽量覆盖至少两个独立来源。"
            "对重复报道去重；每条保留 published_at、title、source、url、summary 和影响方向。"
            "如果窗口内确实没有相关新闻，items 可以为空，但仍应完成多来源搜索并在 coverage_note 说明。"
            "只有完成了系统搜索后 coverage_complete 才能为 true。"
        ),
        input={
            "target": target,
            "market_latest": market_meta["latest"],
            "market_feature_summary": features,
        },
        output_schema=NewsResearch,
    )

    # Stage 5: code checks evidence quality; incomplete news research loops back
    # to another host web-research task.
    for research_round in range(max_research_rounds):
        evidence_check = step(
            run_json_script,
            str(HERE / "evaluate_evidence.py"),
            "--target-json",
            json.dumps(target, ensure_ascii=False),
            "--market-json",
            json.dumps(market, ensure_ascii=False),
            "--news-json",
            json.dumps(news_to_dict(news), ensure_ascii=False),
        )
        if evidence_check["status"] == "ready":
            break

        supplement = agent(
            task=(
                "补充最近新闻证据。严格保持 input.target 指定的新闻时间窗口，"
                "针对 input.problems 重新搜索并补齐来源、URL、发布日期或覆盖范围。"
                "只返回这个时间窗口内的新增证据；不要扩大到历史新闻。"
            ),
            input={
                "target": target,
                "problems": evidence_check["problems"],
                "existing_news": news_to_dict(news),
            },
            output_schema=NewsResearch,
        )
        news = merge_news(news, supplement)

    # Stage 6: multi-angle semantic analysis. The program describes independent
    # tracks; actual subagent creation/concurrency belongs entirely to the host.
    final_analysis = None
    for analysis_round in range(max_research_rounds + 1):
        final_analysis = agent(
            task=(
                "基于 input 中已经给出的 K线、成交量、换手率、波动数据和最近新闻，"
                "完成一次结构化短期股票分析。不要重新定义分析流程。"
                "以下四个分析方向相互独立："
                "(1) technical/K-line：趋势、均线、区间涨跌和异常交易日；"
                "(2) volume/turnover：成交量、成交额相关变化、换手率和量价配合；"
                "(3) news/event：最近新闻与价格行为是否存在时间和逻辑上的对应；"
                "(4) risk/counter-evidence：寻找与主判断相反的证据和结论失效条件。"
                "如果当前宿主支持 native subagent，请由宿主将这四个方向并发执行后 gather；"
                "如果不支持则串行完成。Looma 不负责创建或调度 subagent。"
                "不要通过 CLI、SDK、API 或 subprocess 启动另一个 Coding Agent。"
                "主宿主 gather 后给出 bullish/neutral/bearish/mixed 的短期倾向、0-100 置信度、"
                "综合结论和后续观察信号。分析必须引用 input 中的具体数据或新闻证据，"
                "不能只给泛泛描述。"
                "如果现有证据不足以形成可靠结论，将 needs_more_research=true，"
                "并给出少量、明确、仅与当前短期判断相关的 research_queries。"
            ),
            input={
                "target": target,
                "market_rows": market["rows"],
                "market_features": features,
                "recent_news": news_to_dict(news),
                "analysis_round": analysis_round + 1,
            },
            output_schema=AnalysisRound,
        )

        if not final_analysis.needs_more_research:
            break

        if analysis_round >= max_research_rounds:
            break

        supplement = agent(
            task=(
                "执行 input.research_queries 指定的定向事实核查。"
                "使用当前宿主原生 web/search/browser 能力，仍然优先近期和一手来源。"
                "本步骤只补充与当前分析缺口直接相关的证据，不重新做完整股票分析。"
                "返回的新闻证据仍必须落在 input.target 的 recent-news 时间窗口内；"
                "如果某查询无法在该窗口内找到证据，应在 coverage_note 中明确说明。"
            ),
            input={
                "target": target,
                "research_queries": final_analysis.research_queries,
                "existing_news": news_to_dict(news),
            },
            output_schema=NewsResearch,
        )
        news = merge_news(news, supplement)

    assert final_analysis is not None

    # Stage 7: deterministic rendering.
    return step(
        run_json_script,
        str(HERE / "render_report.py"),
        "--target-json",
        json.dumps(target, ensure_ascii=False),
        "--features-json",
        json.dumps(features, ensure_ascii=False),
        "--news-json",
        json.dumps(news_to_dict(news), ensure_ascii=False),
        "--analysis-json",
        json.dumps(asdict(final_analysis), ensure_ascii=False),
        "--workdir",
        str(root),
    )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--name", default="宇树科技")
    parser.add_argument("--symbol", default="688836")
    parser.add_argument("--workdir", required=True)
    parser.add_argument("--as-of", default=None)
    parser.add_argument("--news-days", type=int, default=3)
    parser.add_argument("--market-days", type=int, default=20)
    parser.add_argument("--max-research-rounds", type=int, default=2)
    parser.add_argument("--market-fixture", default=None, help=argparse.SUPPRESS)
    args = parser.parse_args()

    from datetime import date

    result = analyze_stock(
        name=args.name,
        symbol=args.symbol,
        workdir=args.workdir,
        as_of=args.as_of or date.today().isoformat(),
        news_days=args.news_days,
        market_days=args.market_days,
        max_research_rounds=args.max_research_rounds,
        market_fixture=args.market_fixture,
    )
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
