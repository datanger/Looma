"""Integrated AEP stock-analysis Agent.

Code owns control flow and deterministic calculations.
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
from looma.optimization import (
    Candidate,
    EvaluationBatch,
    OptimizationState,
    candidate_id,
    select_candidate,
)
from looma.optimization.engine import request_reflection
from looma.optimization.state import accept_proposal


HERE = Path(__file__).resolve().parent
DEFAULT_ANALYSIS_INSTRUCTION = (
    "Analyze all four tracks and summarize the available evidence."
)


@dataclass
class MarketRow:
    date: str
    open: float
    close: float
    high: float
    low: float
    volume: float
    turnover_value: float | None
    turnover_rate_pct: float


@dataclass
class MarketDataResearch:
    coverage_complete: bool
    source_urls: list[str]
    source_note: str
    rows: list[MarketRow]


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
    market_evidence: list[str]
    news_evidence_urls: list[str]
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


def market_research_to_dict(value: MarketDataResearch) -> dict:
    return asdict(value)


def analysis_evaluation(
    analysis: AnalysisRound,
    validation: dict,
) -> EvaluationBatch:
    """Turn deterministic analysis validation into GEPA evaluation evidence."""

    ready = validation["status"] == "ready"
    return EvaluationBatch(
        outputs=[asdict(analysis)],
        scores=[1.0 if ready else 0.0],
        side_information=[
            {
                "validation_status": validation["status"],
                "problems": validation["problems"],
            }
        ],
        metric_calls=1,
    )


def request_analysis(
    *,
    target: dict,
    market: dict,
    features: dict,
    news: NewsResearch,
    evidence_check: dict,
    analysis_problems: list[str],
    analysis_round: int,
    strategy: Candidate,
) -> AnalysisRound:
    """Ask the current Host Agent for an analysis under one candidate strategy."""

    return agent(
        task=(
            "基于 input 中已经给出的真实 K线、成交量、换手率、波动数据和最近新闻，"
            "完成一次结构化短期股票分析。不要重新定义分析流程，也不要补造 input 中不存在的数据。"
            "以下四个分析方向相互独立："
            "(1) technical/K-line：趋势、均线、区间涨跌和异常交易日；"
            "(2) volume/turnover：成交量、成交额相关变化、换手率和量价配合；"
            "(3) news/event：最近新闻与价格行为是否存在时间和逻辑上的对应；"
            "(4) risk/counter-evidence：寻找与主判断相反的证据和结论失效条件。"
            "如果当前宿主支持 native subagent，请由宿主将这四个方向并发执行后 gather；"
            "如果不支持则串行完成。Looma 不负责创建或调度 subagent。"
            "不要通过 CLI、SDK、API 或 subprocess 启动另一个 Coding Agent。"
            "market_evidence 必须列出本次判断实际引用的具体日期/数值观察；"
            "news_evidence_urls 只能引用 input.recent_news 中真实存在的 URL。"
            "主宿主 gather 后给出 bullish/neutral/bearish/mixed 的短期倾向、0-100 置信度、"
            "综合结论和后续观察信号。"
            "如果现有证据不足以形成可靠结论，将 needs_more_research=true，"
            "并给出少量、明确、仅与当前短期判断相关的 research_queries。"
            f"本轮分析策略 candidate.analysis_instruction：{strategy['analysis_instruction']}"
        ),
        input={
            "target": target,
            "market_source": {
                "source": market.get("source"),
                "source_urls": market.get("source_urls", []),
            },
            "market_rows": market["rows"],
            "market_features": features,
            "recent_news": news_to_dict(news),
            "news_evidence_check": evidence_check,
            "previous_validation_problems": analysis_problems,
            "analysis_round": analysis_round,
            "analysis_strategy": strategy,
        },
        output_schema=AnalysisRound,
    )


def request_targeted_research(
    *,
    target: dict,
    research_queries: list[str],
    analysis_validation_problems: list[str],
    existing_news: NewsResearch,
) -> NewsResearch:
    """Ask the current Host Agent for evidence targeted by analysis feedback."""

    return agent(
        task=(
            "执行 input.research_queries 指定的定向事实核查。"
            "使用当前宿主原生 web/search/browser 能力，仍然优先近期和一手来源。"
            "本步骤只补充与当前分析缺口直接相关的真实证据，不重新做完整股票分析。"
            "返回的新闻证据仍必须落在 input.target 的 recent-news 时间窗口内；"
            "如果某查询无法在该窗口内找到证据，应在 coverage_note 中明确说明，不能编造。"
        ),
        input={
            "target": target,
            "research_queries": research_queries,
            "analysis_validation_problems": analysis_validation_problems,
            "existing_news": news_to_dict(existing_news),
        },
        output_schema=NewsResearch,
    )


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
    force_market_fallback: bool,
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

    # Stage 2: try AKShare first. A provider/package/network failure is not fatal:
    # the workflow yields a host-native web research task for sourced REAL data.
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
    if force_market_fallback:
        market_args.append("--force-fallback")

    market_meta = step(
        run_json_script,
        str(HERE / "fetch_market_data.py"),
        *market_args,
    )

    if market_meta["status"] != "ready":
        fallback_problems = [market_meta["reason"]]
        previous_research = None

        for market_round in range(max_research_rounds + 1):
            market_research = agent(
                task=(
                    f"AKShare 未能取得 {target['name']} ({target['symbol']}) 的行情。"
                    "请使用当前宿主原生 web/search/browser 能力联网查找真实历史交易数据作为 fallback。"
                    "禁止编造、插值、估算或生成模拟价格；最终分析只能使用可以从公开来源核验的真实数据。"
                    f"目标是取得截至 {target['market_fetch_end']} 最近 {target['market_days']} 个交易日，"
                    "至少 5 个交易日的 date/open/close/high/low/volume/turnover_rate_pct，"
                    "turnover_value 若来源确实没有可为 null。"
                    "优先交易所、行情站点或可信财经数据页；至少记录实际访问的 source_urls。"
                    "如果多个来源数值冲突，应继续核验，不要自行猜测。"
                    "只有数据已经逐项核验后 coverage_complete 才能为 true。"
                    "不得通过 CLI、SDK、API 或 subprocess 启动另一个 Coding Agent。"
                ),
                input={
                    "target": target,
                    "akshare_failure": market_meta,
                    "validation_problems": fallback_problems,
                    "previous_research": previous_research,
                    "market_round": market_round + 1,
                },
                output_schema=MarketDataResearch,
            )
            previous_research = market_research_to_dict(market_research)

            market_meta = step(
                run_json_script,
                str(HERE / "persist_market_data.py"),
                "--symbol",
                target["symbol"],
                "--research-json",
                json.dumps(previous_research, ensure_ascii=False),
                "--market-days",
                str(target["market_days"]),
                "--output",
                str(root / "market-data.json"),
            )
            if market_meta["status"] == "ready":
                break

            fallback_problems = market_meta["problems"]

        if market_meta["status"] != "ready":
            raise RuntimeError(
                "AKShare failed and the host could not obtain enough sourced real market data. "
                "The workflow refuses to fabricate a market series."
            )

    market = load_json(market_meta["market_file"])

    # Stage 3: deterministic feature engineering over the sourced market rows.
    features = step(
        run_json_script,
        str(HERE / "build_market_features.py"),
        "--market",
        market_meta["market_file"],
        "--output",
        str(root / "market-features.json"),
    )

    # Stage 4: the current host performs recent-news web research.
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
            "market_source": {
                "source": market.get("source"),
                "source_urls": market.get("source_urls", []),
            },
            "market_latest": market_meta["latest"],
            "market_feature_summary": features,
        },
        output_schema=NewsResearch,
    )

    # Stage 5: deterministic evidence gate. Every supplement is checked again.
    evidence_check = None
    for research_round in range(max_research_rounds + 1):
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
        if research_round >= max_research_rounds:
            break

        supplement = agent(
            task=(
                "补充最近新闻证据。严格保持 input.target 指定的新闻时间窗口，"
                "针对 input.problems 重新搜索并补齐来源、URL、发布日期或覆盖范围。"
                "只返回这个时间窗口内的新增真实证据；不要扩大到历史新闻，也不要编造新闻。"
            ),
            input={
                "target": target,
                "problems": evidence_check["problems"],
                "existing_news": news_to_dict(news),
            },
            output_schema=NewsResearch,
        )
        news = merge_news(news, supplement)

    assert evidence_check is not None

    # Stage 6: multi-angle semantic analysis plus a bounded GEPA-style strategy
    # refinement loop. Looma describes independent work; actual subagent
    # creation/concurrency belongs entirely to the current host.
    analysis_state = OptimizationState.initialize(
        {"analysis_instruction": DEFAULT_ANALYSIS_INSTRUCTION},
        max_iterations=max(1, max_research_rounds + 1),
        max_metric_calls=max(2, 2 * (max_research_rounds + 1)),
        score_threshold=1.0,
        no_improvement_patience=1,
    )
    final_analysis = None
    analysis_ready = False
    analysis_problems: list[str] = []

    for analysis_round in range(max_research_rounds + 1):
        if analysis_state.should_stop:
            break

        analysis_candidate = select_candidate(analysis_state)
        final_analysis = request_analysis(
            target=target,
            market=market,
            features=features,
            news=news,
            evidence_check=evidence_check,
            analysis_problems=analysis_problems,
            analysis_round=analysis_round + 1,
            strategy=analysis_candidate,
        )

        analysis_validation = step(
            run_json_script,
            str(HERE / "validate_analysis.py"),
            "--analysis-json",
            json.dumps(asdict(final_analysis), ensure_ascii=False),
            "--news-json",
            json.dumps(news_to_dict(news), ensure_ascii=False),
        )
        analysis_problems = analysis_validation["problems"]

        if (
            not final_analysis.needs_more_research
            and analysis_validation["status"] == "ready"
        ):
            analysis_ready = True
            break

        if analysis_round >= max_research_rounds:
            break

        if final_analysis.needs_more_research:
            supplement = request_targeted_research(
                target=target,
                research_queries=final_analysis.research_queries,
                analysis_validation_problems=analysis_problems,
                existing_news=news,
            )
            news = merge_news(news, supplement)
            continue

        parent_evaluation = analysis_evaluation(final_analysis, analysis_validation)
        proposal = request_reflection(
            task=(
                "分析校验未通过。请根据 input.evaluation 中的 validation problems，"
                "只改进 analysis_instruction 这个已声明组件，并返回一个候选 proposal。"
                "不要修改数据来源、证据门槛、报告状态或其它工作流行为。"
            ),
            candidate=analysis_candidate,
            evaluation=parent_evaluation,
            components_to_update=["analysis_instruction"],
            frontier_ids=analysis_state.frontier.ids,
            metric_calls=parent_evaluation.metric_calls or 0,
            remaining_budget=(
                analysis_state.config.max_metric_calls
                - analysis_state.metric_calls
                - (parent_evaluation.metric_calls or 0)
                if analysis_state.config.max_metric_calls is not None
                else None
            ),
        )

        proposal_analysis = request_analysis(
            target=target,
            market=market,
            features=features,
            news=news,
            evidence_check=evidence_check,
            analysis_problems=analysis_problems,
            analysis_round=analysis_round + 1,
            strategy=proposal.candidate,
        )
        proposal_validation = step(
            run_json_script,
            str(HERE / "validate_analysis.py"),
            "--analysis-json",
            json.dumps(asdict(proposal_analysis), ensure_ascii=False),
            "--news-json",
            json.dumps(news_to_dict(news), ensure_ascii=False),
        )
        proposal_evaluation = analysis_evaluation(
            proposal_analysis,
            proposal_validation,
        )
        accepted = step(
            accept_proposal,
            analysis_state,
            proposal,
            scores={"analysis_validation": proposal_evaluation.scores[0]},
            parent_scores={"analysis_validation": parent_evaluation.scores[0]},
            metric_calls=(
                (parent_evaluation.metric_calls or 0)
                + (proposal_evaluation.metric_calls or 0)
            ),
            parent_candidate_id=candidate_id(analysis_candidate),
        )
        final_analysis = proposal_analysis
        analysis_validation = proposal_validation
        analysis_problems = proposal_validation["problems"]

        if not accepted["accepted"]:
            break

        analysis_state = OptimizationState.from_json(accepted["state"])
        if proposal_analysis.needs_more_research:
            supplement = request_targeted_research(
                target=target,
                research_queries=proposal_analysis.research_queries,
                analysis_validation_problems=analysis_problems,
                existing_news=news,
            )
            news = merge_news(news, supplement)
            continue

        if proposal_validation["status"] == "ready":
            analysis_ready = True
            break

    assert final_analysis is not None

    # Re-check the final merged news set, including any analysis-driven research.
    final_evidence_check = step(
        run_json_script,
        str(HERE / "evaluate_evidence.py"),
        "--target-json",
        json.dumps(target, ensure_ascii=False),
        "--market-json",
        json.dumps(market, ensure_ascii=False),
        "--news-json",
        json.dumps(news_to_dict(news), ensure_ascii=False),
    )

    report_status = (
        "complete"
        if analysis_ready and final_evidence_check["status"] == "ready"
        else "insufficient_evidence"
    )

    # Stage 7: deterministic rendering. The program, not the Agent, decides
    # whether the final artifact qualifies as complete.
    return step(
        run_json_script,
        str(HERE / "render_report.py"),
        "--status",
        report_status,
        "--target-json",
        json.dumps(target, ensure_ascii=False),
        "--features-json",
        json.dumps(features, ensure_ascii=False),
        "--news-json",
        json.dumps(news_to_dict(news), ensure_ascii=False),
        "--analysis-json",
        json.dumps(asdict(final_analysis), ensure_ascii=False),
        "--analysis-strategy-json",
        json.dumps(select_candidate(analysis_state), ensure_ascii=False),
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
    parser.add_argument("--force-market-fallback", action="store_true", help=argparse.SUPPRESS)
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
        force_market_fallback=args.force_market_fallback,
    )
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
