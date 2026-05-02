# TraderMoggy — Implementation Plan

> Generated: 2026-05-02  
> Spec: SPEC.md v0.1

---

## Overview

Greenfield Python CLI tool. Two user-facing commands:
- `moggy discover` — ranked buzz table from Reddit + StockTwits
- `moggy research <TICKER>` — parallel 4-agent pipeline → synthesis → saved markdown memo

---

## Dependency Graph

```
T1 (Scaffold)
├── T2 (Market data — yfinance)
├── T3 (Buzz scorer — pure logic)
└── T4 (Social wrappers — PRAW + httpx)
     │
     ├── T5 (Discovery: moggy discover) ← T3 + T4          [CP2]
     │
     ├── T6 (BaseAgent + FundamentalsAgent) ← T2
     ├── T7 (TechnicalAgent + NewsAgent) ← T2
     └── T8 (SocialAgent) ← T4
          │
          └── T9 (SynthesisAgent + Pipeline + moggy research) ← T6+T7+T8  [CP3]
               │
               └── T10 (Polish + CI) ← T5 + T9             [CP4]
```

After T1: T2, T3, T4 are fully independent and can be built in parallel.  
After T4: T5 (needs T3+T4) and T8 can start.  
After T2: T6 and T7 can start.  
T9 waits for T6 + T7 + T8.  
T10 waits for T5 + T9.

---

## Tasks

### T1 — Scaffold  `[CP1]`

**Scope:** Project skeleton — nothing works end-to-end yet except `moggy version`.

| File | Purpose |
|------|---------|
| `pyproject.toml` | uv-compatible; all runtime + dev deps |
| `moggy/__init__.py` | Package root |
| `moggy/cli.py` | Typer app; `version`, `config` commands |
| `moggy/config.py` | `pydantic-settings` Settings; loads `.env`; redacts secrets |
| `moggy/agents/__init__.py` | Namespace init |
| `moggy/data/__init__.py` | Namespace init + `DataError` export |
| `moggy/buzz/__init__.py` | Namespace init |
| `moggy/research/__init__.py` | Namespace init |
| `moggy/output/__init__.py` | Namespace init |
| `.env.example` | All config keys with placeholder values |
| `.gitignore` | Python + `output/` + `.env` |

**Dependencies in `pyproject.toml`:**
```toml
[dependencies]
anthropic = ">=0.49"
typer = ">=0.15"
rich = ">=13"
praw = ">=7"
httpx = ">=0.27"
yfinance = ">=0.2"
pandas-ta = ">=0.3"
pydantic-settings = ">=2"
python-dotenv = ">=1"

[dev-dependencies]
pytest = ">=8"
pytest-asyncio = ">=0.24"
pytest-mock = ">=3"
respx = ">=0.21"
ruff = ">=0.4"
```

**Acceptance criteria:**
- `uv run moggy version` → `TraderMoggy v0.1.0`
- `uv run moggy --help` → lists commands
- `uv run moggy config` → prints config with secrets redacted (shows `***`)

**Verification:** `uv run moggy version && uv run moggy --help`

---

### T2 — Market Data Wrapper

**Scope:** Typed async wrapper around yfinance. No agents, no LLM.

**File:** `moggy/data/market.py`

```
MarketClient
  ├── get_fundamentals(ticker: str) -> FundamentalsData | DataError
  ├── get_ohlcv(ticker: str, period: str = "6mo") -> pd.DataFrame | DataError
  └── get_news(ticker: str, limit: int = 10) -> list[NewsItem] | DataError

FundamentalsData: ticker, pe_ratio, revenue_growth, gross_margin, debt_to_equity
NewsItem: title, publisher, link, published_at
```

Key implementation notes:
- All yfinance calls wrapped in `asyncio.to_thread()`
- Session-level cache: `dict[tuple[str, str], Any]` keyed by `(ticker, method_name)`
- Any exception → `DataError(source="yfinance", message=str(e))`

**Test file:** `tests/unit/test_market.py` — `pytest-mock` patches `yfinance.Ticker`

**Acceptance criteria:**
- All three methods return typed models or `DataError` (never raise)
- Cache hit skips second yfinance call (verifiable via mock call count)
- Unit tests pass with zero network calls

---

### T3 — Buzz Scorer

**Scope:** Pure business logic. No I/O of any kind.

**File:** `moggy/buzz/scorer.py`

```python
@dataclass
class BuzzInput:
    ticker: str
    mention_count_24h: int
    avg_daily_mentions_7d: float
    mentions_last_4h: int
    mentions_prev_4h: int
    positive: int
    negative: int
    total_mentions: int

@dataclass
class BuzzScore:
    ticker: str
    mentions: int
    vol_ratio: float
    velocity_ratio: float
    sentiment: float
    buzz_score: float

def compute_buzz_score(inp: BuzzInput) -> BuzzScore: ...
```

Formula (exact from spec):
```
volume_ratio   = mention_count_24h / (avg_daily_mentions_7d + 1)
velocity_ratio = (mentions_last_4h - mentions_prev_4h) / (mentions_prev_4h + 1)
sentiment      = (positive - negative) / (total_mentions + 1)
buzz_score     = round(volume_ratio * (1 + max(velocity_ratio, 0)) * (1 + 0.5 * sentiment), 2)
```

**Test file:** `tests/unit/test_scorer.py`

Key test cases:
- Spec example: NVDA with vol_ratio=4.2, velocity=1.8, sentiment≈0 → 22.68
- Negative velocity → clamped to 0 (no penalty below baseline)
- Zero mentions baseline (avg_7d=0) → no division by zero

**Acceptance criteria:**
- Formula matches spec identically
- All edge cases (zero denominators, negative velocity) handled
- Pure unit tests, no I/O

---

### T4 — Social Data Wrappers

**Scope:** Reddit (PRAW) + StockTwits (httpx) async wrappers returning typed data.

**Files:**
```
moggy/data/reddit.py     → RedditClient
moggy/data/stocktwits.py → StockTwitsClient
```

```
RedditClient
  └── get_mentions(tickers: list[str], subreddits: list[str]) -> dict[str, MentionData]

StockTwitsClient
  └── get_mentions(ticker: str) -> MentionData | DataError

MentionData: ticker, count_24h, avg_7d, last_4h, prev_4h, positive, negative, total
```

Implementation notes:
- PRAW blocking calls → `asyncio.to_thread()`
- `random.uniform(0.5, 1.5)` jitter between subreddit scans
- StockTwits: `httpx.AsyncClient`, public endpoint, jitter between requests
- Failure → `DataError`, never raise

**Test file:** `tests/unit/test_social.py`
- `respx` mocks httpx for StockTwits
- `pytest-mock` mocks PRAW for Reddit

**Acceptance criteria:**
- Both return `MentionData` or `DataError`; no unhandled exceptions
- Jitter present (mock `random.uniform`, assert it was called)
- Zero network calls in unit tests

---

### T5 — Discovery Mode  `[CP2]`

**Scope:** Wire together T3 + T4 into `moggy discover`. First runnable user-facing feature.

**Files:**
```
moggy/buzz/discovery.py  → DiscoveryScanner
moggy/output/table.py   → render_discovery_table()
```

```
DiscoveryScanner
  └── scan(tickers, sources, limit, min_score) -> list[BuzzScore]
      # fetches Reddit + StockTwits, merges MentionData, calls compute_buzz_score()
      # sorts descending by buzz_score, applies limit + min_score filter
```

```
render_discovery_table(results: list[BuzzScore], limit: int, min_score: float) -> None
  # Rich Table with: Rank, Ticker, Mentions, Vol Ratio (×), Velocity (+/-×), Buzz Score
```

CLI addition in `moggy/cli.py`:
```python
@app.command()
def discover(
    sources: str = "reddit,stocktwits",
    limit: int = 15,
    min_score: float = 0.0,
): ...
```

**Acceptance criteria:**
- `moggy discover --limit 5` → Rich table, sorted descending, in < 30 s
- `--min-score 10.0` → filters below threshold
- One source failure → other source used, gap logged via `rich.console` warning
- `moggy discover --sources reddit` → only Reddit queried

**Checkpoint verification:** `moggy discover --limit 5`

---

### T6 — BaseAgent + FundamentalsAgent

**Scope:** Agent foundation + first concrete agent.

**Files:**
```
moggy/agents/base.py          → BaseAgent, AgentReport
moggy/agents/fundamentals.py → FundamentalsAgent
```

```python
@dataclass
class AgentReport:
    agent_name: str
    ticker: str
    markdown_content: str
    error: str | None = None

class BaseAgent(ABC):
    def __init__(self, client: anthropic.AsyncAnthropic, model: str, market: MarketClient): ...
    @abstractmethod
    async def run(self, ticker: str) -> AgentReport: ...
```

`FundamentalsAgent.run()`:
1. `await market.get_fundamentals(ticker)` → if `DataError`, return error `AgentReport`
2. Build prompt with P/E, revenue growth, gross margin, debt/equity
3. `await client.messages.create(...)` → extract text
4. Return `AgentReport` with markdown content for `## Fundamentals` section

**Test file:** `tests/unit/test_agents.py` (shared file, add to in T7/T8)

**Acceptance criteria:**
- `DataError` from market → `AgentReport` with `error` set (no exception)
- LLM exception → `AgentReport` with `error` set (no exception)
- Markdown content non-empty on success
- No live API calls in tests

---

### T7 — TechnicalAgent + NewsAgent

**Scope:** Two more concrete agents using `MarketClient`.

**Files:**
```
moggy/agents/technical.py → TechnicalAgent
moggy/agents/news.py      → NewsAgent
```

`TechnicalAgent.run()`:
1. `await market.get_ohlcv(ticker)` → compute RSI(14), MACD(12,26,9), BB(20,2) via `pandas-ta`
2. Build prompt with indicator values + recent close prices
3. Claude call → `AgentReport` for `## Technical Picture`

`NewsAgent.run()`:
1. `await market.get_news(ticker, limit=10)`
2. Build prompt with headlines + publishers
3. Claude call → `AgentReport` for `## Recent News`

**Acceptance criteria:**
- `pandas-ta` indicator computation tested with a 200-row OHLCV fixture (fixed CSV)
- Both agents return `AgentReport`; failures captured, not raised
- No live API calls in tests

---

### T8 — SocialAgent

**Scope:** Social data agent combining Reddit + StockTwits for a single ticker.

**File:** `moggy/agents/social.py` → `SocialAgent`

`SocialAgent.run()`:
1. `await reddit.get_mentions([ticker], subreddits=DEFAULT_SUBREDDITS)`
2. `await stocktwits.get_mentions(ticker)`
3. Merge sentiment, build top posts summary
4. Claude call → `AgentReport` for `## Social Sentiment`

**Acceptance criteria:**
- Both sources failing → `AgentReport` with error noted in content (not crashed)
- Returns sentiment summary with mention counts + qualitative tone
- No live API calls in tests

---

### T9 — SynthesisAgent + Pipeline + `moggy research`  `[CP3]`

**Scope:** The full deep-dive pipeline. Biggest task.

**Files:**
```
moggy/agents/synthesis.py  → SynthesisAgent
moggy/research/pipeline.py → ResearchPipeline
moggy/output/memo.py       → save_memo()
```

`ResearchPipeline.run(ticker, model, output_dir)`:
```python
reports = await asyncio.gather(
    social_agent.run(ticker),
    fundamentals_agent.run(ticker),
    technical_agent.run(ticker),
    news_agent.run(ticker),
    return_exceptions=True,
)
# convert exceptions → error AgentReport, log warnings
synthesis_report = await synthesis_agent.run(ticker, reports)
path = save_memo(ticker, synthesis_report.markdown_content, output_dir)
return ResearchResult(ticker, path, reports, synthesis_report)
```

`SynthesisAgent.run(ticker, reports)`:
- Assembles all four `AgentReport` markdown_content values as context
- Prompt: produce memo with exact 6-section structure from spec
- Explicitly forbid buy/sell/hold language in system prompt
- Always appends `*Not financial advice.*`

`save_memo(ticker, content, output_dir)`:
- Creates dir if needed
- Writes `{output_dir}/{TICKER}_{YYYY-MM-DD}.md`
- Returns `Path`

CLI addition: `moggy research <ticker> [--output dir] [--model model]`

**Acceptance criteria:**
- `moggy research AAPL` → saves memo to `./output/AAPL_<date>.md` in < 90 s
- Memo has all 6 sections + disclaimer line
- One agent exception → pipeline continues, gap noted in synthesis prompt
- `--model claude-opus-4-7` overrides default

**Checkpoint verification:** `moggy research AAPL && cat output/AAPL_$(date +%Y-%m-%d).md`

---

### T10 — Polish + CI  `[CP4]`

**Scope:** Robustness, rate-limiting, spinners, CI config.

**Checklist:**
- [ ] Audit all data wrappers: confirm no unhandled `Exception` can escape
- [ ] Add `with Progress(...)` Rich spinner to `discover` and `research` commands
  - `research`: show per-agent status (Social ✓, Fundamentals ✓, etc.)
- [ ] Verify jitter in Reddit + StockTwits (already in T4; audit + add to discovery scan)
- [ ] Add session-level yfinance cache (already specified in T2; audit it's wired to pipeline)
- [ ] `tests/integration/test_pipeline.py`:
  - `@pytest.mark.integration`
  - Live call to `moggy research AAPL` end-to-end
  - Assert memo file exists and contains all section headers
- [ ] `pyproject.toml` `[tool.pytest.ini_options]`: register `integration` marker
- [ ] `.github/workflows/ci.yml`:
  ```yaml
  - run: uv run pytest tests/unit/ -v
  - run: uv run ruff check moggy/
  - run: uv run ruff format --check moggy/
  ```
- [ ] README: install steps, quickstart, `.env` setup guide

**Acceptance criteria:**
- `pytest tests/unit/` → all pass, zero failures
- `ruff check moggy/` → zero errors
- `ruff format --check moggy/` → zero reformats needed
- `moggy research AAPL` shows per-agent spinner
- Integration test passes against live APIs (manual run)

---

## Checkpoints Summary

| CP | After | Gate |
|----|-------|------|
| **CP1** | T1 | `moggy version` prints version; `moggy config` redacts secrets |
| **CP2** | T5 | `moggy discover --limit 5` prints Rich table in < 30 s |
| **CP3** | T9 | `moggy research AAPL` saves 6-section memo in < 90 s |
| **CP4** | T10 | Unit CI green; ruff clean; integration test passes |

---

## Key Constraints

- All I/O: `async`/`await`; blocking calls via `asyncio.to_thread()`
- Inter-layer payloads: dataclasses or Pydantic models (no raw dicts)
- Fetch failures: return `DataError`, never raise
- Agent failures: `AgentReport` with `error` set; pipeline continues
- Output: never buy/sell/hold; always append `*Not financial advice.*`
- Secrets: only in `.env`; never logged, never hardcoded
- Style: 100-char line length, `ruff format`, `ruff check`
- Default LLM model: `claude-sonnet-4-6`
