# TraderMoggy — Task List

> Status key: `[ ]` pending · `[~]` in progress · `[x]` done

---

## Phase 1 — Foundation

- [ ] **T1** Scaffold: pyproject.toml, package dirs, config, CLI skeleton, .env.example, .gitignore
  - Gate: `moggy version` prints version; `moggy config` redacts secrets

---

## Phase 2 — Data Layer  *(parallel after T1)*

- [ ] **T2** Market data wrapper: `moggy/data/market.py` (yfinance, async, cache, DataError)
  - `tests/unit/test_market.py` with mocked yfinance
- [ ] **T3** Buzz scorer: `moggy/buzz/scorer.py` (pure formula, BuzzInput, BuzzScore)
  - `tests/unit/test_scorer.py` (deterministic, no I/O)
- [ ] **T4** Social wrappers: `moggy/data/reddit.py` + `moggy/data/stocktwits.py` (jitter, DataError)
  - `tests/unit/test_social.py` with respx + pytest-mock

---

## Phase 3 — Discovery  `[CP2]`

- [ ] **T5** Discovery mode: `moggy/buzz/discovery.py` + `moggy/output/table.py` + `moggy discover` CLI
  - Gate: `moggy discover --limit 5` → Rich table in < 30 s

---

## Phase 4 — Deep-Dive Agents  *(parallel after T2/T4)*

- [ ] **T6** BaseAgent + FundamentalsAgent: `moggy/agents/base.py` + `moggy/agents/fundamentals.py`
  - `tests/unit/test_agents.py` (mocked LLM)
- [ ] **T7** TechnicalAgent + NewsAgent: `moggy/agents/technical.py` + `moggy/agents/news.py`
  - pandas-ta indicators from fixed OHLCV fixture; mocked LLM
- [ ] **T8** SocialAgent: `moggy/agents/social.py`
  - Both sources fail → error AgentReport, not crash; mocked LLM

---

## Phase 5 — Pipeline  `[CP3]`

- [ ] **T9** SynthesisAgent + Pipeline + `moggy research`: `moggy/agents/synthesis.py` +
  `moggy/research/pipeline.py` + `moggy/output/memo.py` + CLI command
  - Gate: `moggy research AAPL` → saves 6-section memo in < 90 s

---

## Phase 6 — Polish + CI  `[CP4]`

- [ ] **T10** Polish + CI:
  - [ ] Audit DataError propagation across all wrappers
  - [ ] Rich Progress spinners (discover + research per-agent status)
  - [ ] Integration test: `tests/integration/test_pipeline.py` (live AAPL)
  - [ ] pytest marker config in pyproject.toml
  - [ ] GitHub Actions CI: pytest unit + ruff check + ruff format --check
  - [ ] README quickstart

---

## Stretch (Phase 6 — out of scope for v1)

- [ ] X/Twitter data source
- [ ] Web UI (FastAPI + HTMX)
- [ ] Scheduled polling / cron mode
