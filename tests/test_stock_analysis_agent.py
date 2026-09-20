import json
import os
import subprocess
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC = PROJECT_ROOT / "src"
WORKFLOW = PROJECT_ROOT / "examples" / "stock_analysis_agent" / "workflow.py"


def _run(command, *, cwd: Path, env: dict[str, str]):
    return subprocess.run(
        command,
        cwd=cwd,
        env=env,
        text=True,
        capture_output=True,
    )


def _latest_request(run_dir: Path) -> Path:
    requests = sorted((run_dir / "events").glob("*-script2agent.json"))
    assert requests
    return requests[-1]


def _resume(
    *,
    request_file: Path,
    response_file: Path,
    result: dict,
    cwd: Path,
    env: dict[str, str],
):
    request = json.loads(request_file.read_text(encoding="utf-8"))
    Path(request["output"]["result_file"]).write_text(
        json.dumps(result, ensure_ascii=False),
        encoding="utf-8",
    )
    response_file.write_text(
        json.dumps(request["expected_output"]),
        encoding="utf-8",
    )
    completed = _run(
        [
            sys.executable,
            "-m",
            "looma.cli",
            "handoff",
            "--request",
            str(request_file),
            "--response",
            str(response_file),
        ],
        cwd=cwd,
        env=env,
    )
    return completed, request


def _market_fixture(path: Path) -> None:
    rows = []
    closes = [210, 214, 212, 218, 225, 231, 228, 236, 244, 252]
    volumes = [120, 130, 125, 145, 170, 210, 180, 260, 320, 350]
    turnovers = [4.2, 4.4, 4.1, 4.8, 5.2, 6.1, 5.5, 7.2, 8.4, 9.1]

    for index, (close, volume, turnover) in enumerate(zip(closes, volumes, turnovers), start=9):
        rows.append(
            {
                "date": f"2026-09-{index:02d}",
                "open": close - 2,
                "close": close,
                "high": close + 4,
                "low": close - 5,
                "volume": volume,
                "turnover_value": volume * close * 1000,
                "amplitude_pct": 4.0 + (index % 3),
                "change_pct": 2.0 + (index % 4),
                "change_value": 4.0,
                "turnover_rate_pct": turnover,
            }
        )

    path.write_text(json.dumps({"rows": rows}, ensure_ascii=False), encoding="utf-8")


def test_stock_analysis_agent_end_to_end_with_research_loop(tmp_path: Path):
    workdir = tmp_path / "work"
    state_dir = tmp_path / "state"
    fixture = tmp_path / "market.json"
    _market_fixture(fixture)

    env = os.environ.copy()
    env["PYTHONPATH"] = str(SRC)
    env["LOOMA_STATE_DIR"] = str(state_dir)

    command = [
        sys.executable,
        str(WORKFLOW),
        "--name",
        "宇树科技",
        "--symbol",
        "688836",
        "--workdir",
        str(workdir),
        "--as-of",
        "2026-09-20",
        "--news-days",
        "3",
        "--market-days",
        "10",
        "--max-research-rounds",
        "2",
        "--market-fixture",
        str(fixture),
    ]

    # Stage 1-3 run as scripts, then the host is asked to research recent news.
    first = _run(command, cwd=tmp_path, env=env)
    assert first.returncode == 75, first.stderr
    assert (workdir / "market-data.json").exists()
    assert (workdir / "market-features.json").exists()

    run_dir = next((state_dir / "runs").iterdir())
    request1_file = _latest_request(run_dir)
    request1 = json.loads(request1_file.read_text(encoding="utf-8"))
    assert "上网查询" in request1["task"]
    assert "2026-09-18" in request1["task"]
    assert "2026-09-20" in request1["task"]

    news_result = {
        "window_start": "2026-09-18",
        "window_end": "2026-09-20",
        "search_queries": ["宇树科技 688836 2026-09-20", "宇树科技 公告"],
        "searched_sources": ["上海证券交易所", "财经媒体A"],
        "items": [
            {
                "published_at": "2026-09-18",
                "title": "宇树科技近期公告A",
                "source": "上海证券交易所",
                "url": "https://example.test/sse-a",
                "summary": "测试用近期公告证据。",
                "impact": "neutral",
            },
            {
                "published_at": "2026-09-19",
                "title": "宇树科技近期新闻B",
                "source": "财经媒体A",
                "url": "https://example.test/news-b",
                "summary": "测试用近期新闻证据。",
                "impact": "positive",
            },
        ],
        "coverage_complete": True,
        "coverage_note": "测试中模拟完成多来源近期新闻检索。",
    }

    second, _ = _resume(
        request_file=request1_file,
        response_file=tmp_path / "agent2script-1.json",
        result=news_result,
        cwd=tmp_path,
        env=env,
    )

    # Evidence validation passes, then the host receives the four-track analysis task.
    assert second.returncode == 75, second.stderr
    request2_file = _latest_request(run_dir)
    assert request2_file != request1_file
    request2 = json.loads(request2_file.read_text(encoding="utf-8"))
    assert "native subagent" in request2["task"]
    assert "并发执行" in request2["task"]
    assert "technical/K-line" in request2["task"]
    assert "volume/turnover" in request2["task"]
    assert "risk/counter-evidence" in request2["task"]

    analysis1 = {
        "needs_more_research": True,
        "research_queries": ["宇树科技 688836 订单 公告 2026-09-18 2026-09-20"],
        "analysis_tracks": [
            "technical/K-line",
            "volume/turnover",
            "news/event",
            "risk/counter-evidence",
        ],
        "technical_view": "价格处于短期上行区间，但样本较短。",
        "volume_turnover_view": "成交量和换手率同步抬升，需要确认事件驱动。",
        "news_event_view": "近期消息可能与放量有关，但证据还不充分。",
        "risk_counterevidence": "新股历史数据短，趋势信号稳定性有限。",
        "short_term_bias": "mixed",
        "confidence": 55,
        "conclusion": "需要补充事件证据后再形成结论。",
        "watch_signals": ["后续成交量是否持续", "事件是否有一手公告确认"],
    }

    third, _ = _resume(
        request_file=request2_file,
        response_file=tmp_path / "agent2script-2.json",
        result=analysis1,
        cwd=tmp_path,
        env=env,
    )

    # The Python analysis loop asks the host for targeted research.
    assert third.returncode == 75, third.stderr
    request3_file = _latest_request(run_dir)
    request3 = json.loads(request3_file.read_text(encoding="utf-8"))
    assert request3_file not in {request1_file, request2_file}
    assert "定向事实核查" in request3["task"]

    supplement = {
        "window_start": "2026-09-18",
        "window_end": "2026-09-20",
        "search_queries": ["宇树科技 688836 订单 公告 2026-09-18 2026-09-20"],
        "searched_sources": ["公司公告", "财经媒体B"],
        "items": [
            {
                "published_at": "2026-09-20",
                "title": "宇树科技补充事件证据C",
                "source": "公司公告",
                "url": "https://example.test/company-c",
                "summary": "测试用定向补充证据。",
                "impact": "positive",
            }
        ],
        "coverage_complete": True,
        "coverage_note": "完成定向事实核查。",
    }

    fourth, _ = _resume(
        request_file=request3_file,
        response_file=tmp_path / "agent2script-3.json",
        result=supplement,
        cwd=tmp_path,
        env=env,
    )

    # The analysis loop runs again with the expanded evidence set.
    assert fourth.returncode == 75, fourth.stderr
    request4_file = _latest_request(run_dir)
    request4 = json.loads(request4_file.read_text(encoding="utf-8"))
    assert request4_file not in {request1_file, request2_file, request3_file}
    assert "technical/K-line" in request4["task"]

    analysis2 = {
        "needs_more_research": False,
        "research_queries": [],
        "analysis_tracks": [
            "technical/K-line",
            "volume/turnover",
            "news/event",
            "risk/counter-evidence",
        ],
        "technical_view": "近期收盘价上行，且最新价格位于短期均线上方。",
        "volume_turnover_view": "近5日成交量与换手率较前5日明显抬升，量价同步偏强。",
        "news_event_view": "近期事件证据与放量时间接近，可作为短期驱动之一。",
        "risk_counterevidence": "上市时间较短、样本有限，且高换手意味着分歧和波动风险仍高。",
        "short_term_bias": "bullish",
        "confidence": 72,
        "conclusion": "短期量价与事件证据偏强，但由于样本短和换手较高，结论需要持续验证。",
        "watch_signals": ["成交量能否维持", "换手率是否快速回落", "是否出现新的正式公告"],
    }

    final, _ = _resume(
        request_file=request4_file,
        response_file=tmp_path / "agent2script-4.json",
        result=analysis2,
        cwd=tmp_path,
        env=env,
    )
    assert final.returncode == 0, final.stderr

    report_json = workdir / "stock-analysis.json"
    report_md = workdir / "stock-analysis.md"
    assert report_json.exists()
    assert report_md.exists()

    report = json.loads(report_json.read_text(encoding="utf-8"))
    assert report["target"]["name"] == "宇树科技"
    assert report["target"]["symbol"] == "688836"
    assert report["market_features"]["sample"]["trading_days"] == 10
    assert report["market_features"]["volume"]["recent5_vs_previous5_pct"] is not None
    assert report["market_features"]["turnover"]["recent5_vs_previous5_pct"] is not None
    assert len(report["recent_news"]["items"]) == 3
    assert report["analysis"]["short_term_bias"] == "bullish"
    assert report["analysis"]["confidence"] == 72

    state = json.loads((run_dir / "state.json").read_text(encoding="utf-8"))
    assert state["status"] == "completed"
    kinds = [event["kind"] for event in state["events"]]
    assert kinds == [
        "step",
        "step",
        "step",
        "agent",
        "step",
        "agent",
        "agent",
        "agent",
        "step",
    ]
