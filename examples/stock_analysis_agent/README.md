# Stock Analysis Agent

This is the single integrated Looma example.

It analyzes a specified A-share stock with a deterministic workflow plus host-native Agent work. The default target is **宇树科技 (688836)**.

The workflow deliberately separates work that should be code from work that should be done by the current Coding Agent host:

```text
resolve_stock.py
      ↓
fetch_market_data.py          <- try AKShare first
      │
      ├─ success ─────────────→ real market rows
      │
      └─ unavailable ─→ agent(): host web research
                           ↓
                    sourced real market rows
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
deterministic analysis validation
      │
      ├─ needs more evidence ─→ agent(): targeted research ─→ loop
      │
      ├─ validation failed ─→ GEPA candidate reflection
      │                              ↓
      │                    proposal analysis + acceptance gate
      │                              │
      │                    revised strategy ─→ loop
      │
      └─ ready ────────────────→
             ↓
render_report.py
      ↓
stock-analysis.md / stock-analysis.json
```

The Agent task describes independent analysis tracks. If the current host supports native subagents, the host may execute those tracks concurrently. Looma itself never launches an Agent, subagent, CLI, SDK, or model API.

The final analysis stage also demonstrates the GEPA-style capability embedded
in AEP. Python keeps an `analysis_instruction` candidate and evaluates each
analysis with the deterministic `validate_analysis.py` gate. When the output
is schema-valid but fails that gate, the current Host Agent receives the
validation problems through `request_reflection()`, proposes a revised
candidate, and the same analysis is replayed under that candidate. Python
accepts the proposal with `accept_proposal()` and only the accepted strategy is
recorded in the final report. Evidence acquisition, report status, and the
final news gate remain program-owned.

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

The example uses daily K-line fields including close/open/high/low, volume, turnover value, amplitude, daily change and turnover rate.

AKShare failure is a recoverable condition. If the package, network, or upstream provider is unavailable, the workflow yields control to the **current host Agent** and asks it to obtain the missing market rows through native web/search/browser tools. That fallback must include source URLs and is explicitly forbidden from inventing, interpolating, or estimating prices. If enough sourced real data still cannot be obtained, the workflow fails instead of fabricating a market series.

Synthetic/fixture market rows exist only in deterministic CI tests; they are not a live-analysis fallback.

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

The final report is written to the selected work directory. Its top-level status is either `complete` or `insufficient_evidence`; the Workflow, not the Agent, decides that status after deterministic news/analysis validation.

This is an analysis workflow example, not personalized investment advice.
