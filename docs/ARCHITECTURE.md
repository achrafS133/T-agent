# Architecture

Deep-dive into how T-AGENT PRO orchestrates multi-agent trading intelligence.

![Agent Pipeline](assets/architecture.svg)

## Pipeline stages

| Stage | Module | Description |
|-------|--------|-------------|
| **1. Data fetch** | `src/data/market_data.py` | Pulls prices, fundamentals, news RSS, and r/WallStreetBets posts |
| **2. Reflection** | `src/data/logger.py` | Injects past decisions for the same ticker into context |
| **3. Analysts** | `src/agents/analysts.py` | Three parallel LLM chains: fundamental, technical, sentiment |
| **4. Debate** | `src/agents/decision_makers.py` | Bull vs bear researchers with second-order thinking |
| **5. Risk** | `src/agents/decision_makers.py` | Flags extreme sentiment and assigns Low/Medium/High risk |
| **6. Portfolio** | `src/agents/decision_makers.py` | Persona-driven structured decision (BUY/SELL/HOLD) |
| **7. Execution** | `src/portfolio.py` | Simulated brokerage with guardrails + stop-loss |

## Orchestration

LangGraph (`src/graph/orchestrator.py`) compiles a state machine:

```
START → fetch_data → reflection → [fundamental, technical, sentiment] → debate → risk → portfolio → END
```

Analyst nodes run **in parallel** after reflection. All three must complete before the debate node fires.

## State model

`TradingState` (`src/state.py`) carries ticker metadata, raw market data, analyst outputs, debate arguments, risk assessment, and the final decision dict.

## Portfolio rules

| Rule | Value | Enforced in |
|------|-------|-------------|
| Max position | 20% of portfolio | `update_portfolio()` |
| Min cash reserve | 20% | `update_portfolio()` |
| Stop-loss | 5% from avg cost | `check_stop_losses()` |
| Broker fee | 0.1% | `update_portfolio()` |
| Trade gate | Confidence must be HIGH | `make_portfolio_decision()` |

## Persistence

| File | Purpose |
|------|---------|
| `storage/logs/portfolio.json` | Cash, holdings, trade history, P&L snapshots |
| `storage/logs/decision_history.md` | Human-readable decision archive |

## API surface

FastAPI (`src/api.py`) exposes REST + WebSocket. Analysis runs in background tasks and broadcasts node progress to connected clients.

## Frontend

React + Vite dashboard (`apps/web/`) proxies `/api` and `/ws` to the backend during development.
