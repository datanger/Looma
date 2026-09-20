# Stock Analysis Agent

This is the single integrated Looma example.

It analyzes a specified A-share stock with a deterministic workflow plus host-native Agent work. The default target is **宇树科技 (688836)**.

The workflow deliberately separates work that should be code from work that should be done by the current Coding Agent host:

```text
resolve_stock.py
      ↓
fetch_market_data.py          <- AKShare, no Agent
      ↓
build_market_features.py      <- deterministic calculations
      ↓
agent(): recent-news research <- host-native web research
      ↓
evaluate_evidence.py
      │
      ├─ incomplete ─→ agent(): targeted research ─┐
      │                                            │
      └────────────────────────────────────────────┘
      ↓
agent(): multi-angle analysis
      ├─ technical/K-line track
      ├─ volume/turnover track
      ├─ news/event track
      └─ risk/counter-evidence track
             ↓
      host-native gather
             ↓
needs more evidence?
      │
      ├─ yes ─→ agent(): targeted research ─→ loop
      │
      └─ no
             ↓
render_report.py
      ↓
stock-analysis.md / stock-analysis.json
```

The Agent task describes independent analysis tracks. If the current host supports native subagents, the host may execute those tracks concurrently. Looma itself never launches an Agent, subagent, CLI, SDK, or model API.

## Data

Market data uses AKShare:

```python
ak.stock_zh_a_hist(
    symbol="688836",
    period="daily",
    start_date="...",
    end_date="...",
    adjust="",
)
```

The example uses the returned daily K-line fields including close/open/high/low, volume, turnover value, amplitude, daily change and turnover rate.

AKShare is an example-only dependency and is not added to Looma Runtime itself:

```bash
pip install -r examples/stock_analysis_agent/requirements.txt
```

No AKShare API key is configured by this example.

## Run

Run from an already-existing Coding Agent host session:

```bash
PYTHONPATH=src \
LOOMA_STATE_DIR=/tmp/looma-stock-state \
python examples/stock_analysis_agent/workflow.py \
  --name 宇树科技 \
  --symbol 688836 \
  --workdir /tmp/looma-stock-analysis
```

Useful options:

```text
--news-days 3       recent calendar-day news window
--market-days 20    recent trading rows used for market analysis
--max-research-rounds 2
--as-of YYYY-MM-DD  make the analysis reproducible
```

The final report is written to the selected work directory.

This is an analysis workflow example, not personalized investment advice.
