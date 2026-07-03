# News-to-Trade Agent — Project CLAUDE.md

Multi-agent LangChain/LangGraph system that reads daily news for the S&P 500,
decides buy/hold/sell, executes paper trades via Alpaca, and logs full
reasoning chains for a portfolio demo. Orchestrated by Ruflo on top of
Claude Code. Token spend is a first-class constraint, not an afterthought.

---

## Stack

- Python 3.11
- LangChain + LangGraph (agent logic, tool calling, RAG)
- Alpaca Paper Trading API — both broker AND news data source (see Data Source note)
- Ruflo (swarm orchestration, memory, hooks) — installed via `npx ruflo@latest init`
- RuVector (Ruflo's memory backend) for caching + pattern memory
- Next.js + Framer Motion (dashboard, phase 2)
- SQLite or Postgres for trade/reasoning log (queryable history for backtest + UI)

---

## Scope

- Universe: S&P 500, refreshed weekly from a static list (Wikipedia table scrape,
  cached — do not re-fetch every run)
- Mode: paper trading only. No live capital, ever, without explicit human flag flip.
- Demo target: multi-week track record with a public reasoning log, not just a
  backtest chart.

---

## Data Source (locked decision — read before changing)

NewsAPI free tier caps at 100 requests/day and is not viable for a 500-ticker
daily scan. Do not build against it.

**Use Alpaca News API instead** — free with the paper account already set up,
same auth as the broker calls, materially higher limits, real-time. One less
credential to manage.

If a richer feed is ever justified (multi-source corroboration, longer history),
evaluate Polygon or Benzinga as a paid upgrade — not a v1 requirement.

---

## Architecture: 2-Tier Pipeline (this is the token-budget mechanism)

Do not point an LLM at 500 tickers a day. The pipeline exists specifically to
keep LLM calls limited to a small, high-signal shortlist.

### Tier 0 — Non-LLM Screener (runs on all 500 tickers, no exceptions)

- Pulls price delta, volume delta, and news-count delta vs. trailing average
- Pure numeric filters, zero LLM calls
- Output: shortlist of ~15–30 tickers/day worth spending tokens on
- Runs pre-market via cron/scheduler

### Tier 1 — LLM Agent Swarm (Ruflo, adaptive topology, shortlist only)

| Agent | Model | Role |
|---|---|---|
| News Analyst | Haiku | Batch-summarize + sentiment-score all headlines per ticker in ONE call, not one call per headline |
| Fundamental Context | — (memory read) | Pull cached fundamentals from RuVector, 7-day TTL, no live re-fetch unless stale |
| Bull / Bear / Risk (debate sub-swarm) | Sonnet | Mesh topology, 3 agents argue the shortlisted ticker, only triggered if \|Δsentiment\| > 0.3 threshold |
| Portfolio / Risk Manager | Sonnet | Hierarchical coordinator — position sizing, max exposure %, correlation check vs. current book |
| Execution | Haiku (tool-call only) | Places Alpaca paper order, writes reasoning chain to log |
| Backtest / Perf | Sonnet, nightly batch | Computes equity curve, writes outcome back to memory as a weighted pattern |

Adaptive topology: hierarchical during Tier 0→1 handoff (coordinator fans out
to News Analyst workers), switches to mesh for the Bull/Bear/Risk debate on
individual shortlisted names, back to hierarchical for Risk Manager → Execution.

---

## Ruflo Config

```bash
npx ruflo@latest swarm init --topology adaptive --max-agents 8 --strategy specialized
```

Model routing (enforce in agent definitions, not just this doc):
- Screener / summarizer / execution → Haiku
- Debate / decision / risk manager → Sonnet
- Orchestrator → Sonnet

Memory namespaces (`ruflo memory store --namespace <name>`):
- `fundamentals` — 7-day TTL, ticker fundamentals
- `headline-cache` — dedupe headlines already summarized, check before any LLM call
- `sentiment-history` — rolling sentiment score per ticker, used by Tier 0 screener
- `trade-reasoning` — full reasoning chain per executed trade, this is the demo artifact

Hooks (auto-route, don't hand-dispatch):
- `new-headline-batch` → News Analyst
- `shortlist-ready` → Bull/Bear/Risk debate swarm
- `decision-made` → Risk Manager → Execution
- `market-close` → Backtest/Perf agent

---

## Token Budget Rules (hard rules — violating these is a bug, not a style choice)

1. NEVER call an LLM per-ticker in Tier 0. Numeric filters only.
2. NEVER re-summarize a headline already in `headline-cache`. Check memory first.
3. NEVER spin up the debate swarm for a ticker below the sentiment-move threshold.
4. ALWAYS batch all headlines for a ticker into one LLM call, not N calls.
5. ALWAYS use Haiku for extraction/summarization. Sonnet only for the actual
   buy/hold/sell decision and risk sizing.
6. Log token spend per agent per run to memory (`namespace: token-spend`).
   Alert if daily spend exceeds the configured cap.

---

## Trading Logic

- Paper only. Alpaca API.
- Max position size: configurable %, default 5% of paper book per name.
- Stop-loss / take-profit rules defined per trade at execution time, not
  discretionary after the fact.
- Max daily trade count cap — prevents runaway execution loops.
- **Every trade must log:** headline(s) used, sentiment score, full debate
  transcript, decision confidence, position-size rationale. This log is the
  actual portfolio deliverable — the equity curve is secondary proof.

---

## File Structure

```
news-trade-agent/
├── CLAUDE.md
├── .env.example
├── pyproject.toml
├── agents/
│   ├── screener.py          # Tier 0, no LLM
│   ├── news_analyst.py      # Haiku, batched summarization
│   ├── debate/
│   │   ├── bull.py
│   │   ├── bear.py
│   │   └── risk.py
│   ├── portfolio_manager.py
│   ├── execution.py
│   └── backtest.py
├── memory/
│   └── ruvector_client.py   # thin wrapper over Ruflo memory calls
├── data/
│   ├── universe.py          # S&P 500 list fetch/cache
│   └── alpaca_client.py     # broker + news, one client
├── graph/
│   └── pipeline.py          # LangGraph wiring, tier 0 → tier 1
├── db/
│   └── models.py            # trade log, reasoning log schema
├── dashboard/                # phase 2, Next.js
└── tests/
    └── test_screener.py
```

---

## Coding Conventions

- Do what's asked, nothing more. No speculative abstraction.
- Prefer editing an existing file over creating a new one.
- Never create documentation files beyond this one unless explicitly requested.
- Type hints on every function signature, Python side.
- One agent = one module = one responsibility. No god-files.
- Every LLM call site must check the relevant memory namespace first if a
  cache rule applies (see Token Budget Rules).

---

## Frontend (Phase 2 — separate build, not blocking agent work)

Direction: motionsites.ai-style — minimalist, classic type, continuous subtle
animation on a dark full-bleed background (reference: night scene, floating
particles/motes, warm focal light — not busy, not looping obviously).

- Next.js + Framer Motion, canvas or WebGL layer for the ambient motion
  (particles drifting, very slow parallax — think "grass moving" reference,
  not "confetti")
- Muted dark palette, serif display type for headlines + clean sans for body
- Live panel: streaming reasoning chain per decision, agent status indicator
  ("swarm active" / idle), equity curve, current positions table
- Motion should read as ambient, not decorative — it should feel alive
  without competing with the data

---

## Testing / Safety

- Backtest mode replays historical Alpaca data + archived news — zero live
  API calls during backtest runs.
- A `--dry-run` flag is required before any order reaches Alpaca, even paper.
  No agent may place an order without this flag explicitly set to false.
- Nightly backtest agent writes outcomes back to memory — this is how the
  system's future weighting improves without manual tuning.

---

## Open Items Before Build Starts

1. Confirmed: Alpaca News API replaces NewsAPI (see Data Source section).
2. Sentiment-move threshold for triggering the debate swarm — default 0.3,
   tune after first week of paper data.
3. Max position size % and max daily trade count — need your numbers before
   `portfolio_manager.py` is written.
