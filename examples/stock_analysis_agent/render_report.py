"""Render the final deterministic stock-analysis artifacts."""

from __future__ import annotations

import argparse
import json
from pathlib import Path


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--target-json", required=True)
    parser.add_argument("--features-json", required=True)
    parser.add_argument("--news-json", required=True)
    parser.add_argument("--analysis-json", required=True)
    parser.add_argument("--workdir", required=True)
    args = parser.parse_args()

    target = json.loads(args.target_json)
    features = json.loads(args.features_json)
    news = json.loads(args.news_json)
    analysis = json.loads(args.analysis_json)

    workdir = Path(args.workdir).resolve()
    workdir.mkdir(parents=True, exist_ok=True)

    payload = {
        "target": target,
        "market_features": features,
        "recent_news": news,
        "analysis": analysis,
        "disclaimer": "This workflow output is informational analysis, not personalized investment advice.",
    }

    json_file = workdir / "stock-analysis.json"
    json_file.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    lines = [
        f"# {target['name']} ({target['symbol']}) 短期股票分析",
        "",
        f"- 分析时点：{target['as_of']}",
        f"- 新闻窗口：{target['news_start']} ~ {target['news_end']}",
        f"- 行情样本：{features['sample']['first_date']} ~ {features['sample']['last_date']}，{features['sample']['trading_days']} 个交易日",
        "",
        "## 市场数据",
        "",
        f"- 最新收盘：{features['price']['latest_close']}",
        f"- 区间涨跌：{features['price']['period_return_pct']}%",
        f"- MA5 / MA10 / MA20：{features['price']['ma5']} / {features['price']['ma10']} / {features['price']['ma20']}",
        f"- 最新成交量：{features['volume']['latest']}",
        f"- 近5日成交量相对前5日：{features['volume']['recent5_vs_previous5_pct']}%",
        f"- 最新换手率：{features['turnover']['latest_pct']}%",
        f"- 近5日换手率相对前5日：{features['turnover']['recent5_vs_previous5_pct']}%",
        "",
        "## 最近新闻",
        "",
    ]

    items = news.get("items", [])
    if items:
        for item in items:
            lines.append(
                f"- {item['published_at']} [{item['title']}]({item['url']}) — {item['source']}：{item['summary']}"
            )
    else:
        lines.append(f"- 在指定窗口内未找到足够明确的相关新闻。{news.get('coverage_note', '')}")

    lines.extend(
        [
            "",
            "## 分析",
            "",
            f"**短期倾向：{analysis['short_term_bias']}**",
            "",
            f"**置信度：{analysis['confidence']}/100**",
            "",
            f"### K线 / 趋势\n{analysis['technical_view']}",
            "",
            f"### 成交量 / 换手率\n{analysis['volume_turnover_view']}",
            "",
            f"### 新闻 / 事件\n{analysis['news_event_view']}",
            "",
            f"### 风险与反向证据\n{analysis['risk_counterevidence']}",
            "",
            f"### 综合结论\n{analysis['conclusion']}",
            "",
            "### 后续观察信号",
        ]
    )
    lines.extend(f"- {item}" for item in analysis.get("watch_signals", []))
    lines.extend(
        [
            "",
            "> 本案例输出仅用于展示 Looma/AEP 工作流，不构成个性化投资建议。",
            "",
        ]
    )

    markdown_file = workdir / "stock-analysis.md"
    markdown_file.write_text("\n".join(lines), encoding="utf-8")

    print(
        json.dumps(
            {
                "report_json": str(json_file),
                "report_markdown": str(markdown_file),
                "short_term_bias": analysis["short_term_bias"],
                "confidence": analysis["confidence"],
                "conclusion": analysis["conclusion"],
            },
            ensure_ascii=False,
        )
    )


if __name__ == "__main__":
    main()
