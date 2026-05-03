# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Commands

```bash
uv sync                                    # install / sync environment
uv run moggy version                       # verify CLI works
uv run moggy config                        # show config (secrets redacted)

uv run pytest tests/unit/ -v              # run unit tests
uv run pytest tests/unit/test_cli.py::test_version_output -v  # single test
uv run pytest -m integration -v           # integration tests (require live APIs)

uv run ruff format moggy/                  # format
uv run ruff check moggy/                   # lint

uv add <package>                           # add runtime dep (updates pyproject.toml + uv.lock)
uv add --dev <package>                     # add dev dep
```

## Architecture

TraderMoggy is a Python 3.12+ CLI that surfaces Reddit/StockTwits buzz, scores it, and produces analyst-style research memos via Claude AI. Entry point: `moggy = "moggy.cli:app"`.

### Package layout

```
moggy/
  cli.py          # Typer app — commands: version, config (+ future: discover, research)
  config.py       # pydantic-settings singleton; get_settings() is @lru_cache
  data/           # Market (yfinance), Reddit (PRAW), StockTwits (httpx) wrappers — T2/T4
  buzz/           # Buzz scoring logic — T3
  agents/         # Four analyst agents (social, fundamental, technical, news) + synthesis — T6-T8
  output/         # Rich table renderer + markdown memo writer — T5/T9
  research/       # Deep-dive pipeline orchestration — T9
```

Tasks T2–T10 are not yet implemented. See `tasks/plan.md` for the dependency graph and acceptance criteria per task.

### Key patterns

**Error handling:** data fetch failures return `DataError(source, message)` — never raise. Agents receive `DataError | ActualData` and handle gracefully so one source failure doesn't abort the pipeline.

**Async I/O:** all external calls are `async`/`await`. Blocking libraries (yfinance, PRAW) are wrapped with `asyncio.to_thread()`.

**Config:** `Settings` (pydantic-settings) loads from `.env`. Secrets are redacted in `.display()`. Always retrieve via `get_settings()` — never instantiate directly.

**Testing:** `tests/conftest.py` has two `autouse` fixtures — one clears the `get_settings()` LRU cache and one `monkeypatch.chdir(tmp_path)` to prevent ambient `.env` pollution. Unit tests mock all I/O (pytest-mock, respx). Integration tests use `@pytest.mark.integration`.

### Code style (enforced by ruff)

- Line length: 100
- Full type annotations on public functions
- `select = ["E", "F", "I", "UP"]` — errors, undefined names, import sort, pyupgrade
- Comments only for non-obvious *why*, never *what*

### Project phases

| Phase | Tasks | Gate |
|-------|-------|------|
| 1 — Foundation | T1 | ✅ CP1 done — `moggy version` works, secrets redacted |
| 2 — Data Layer | T2 (market), T3 (buzz), T4 (social) | can run in parallel |
| 3 — Discovery | T5 | `moggy discover --limit 5` → Rich table |
| 4 — Agents | T6, T7, T8 | four analyst agents + synthesis |
| 5 — Pipeline | T9 | `moggy research AAPL` → saves memo |
| 6 — Polish + CI | T10 | full CI, spinners, integration tests |

### Environment variables

See `.env.example`. Required: `ANTHROPIC_API_KEY`, `REDDIT_CLIENT_ID`, `REDDIT_CLIENT_SECRET`. Optional: `DEFAULT_MODEL` (default `claude-sonnet-4-6`), `DISCOVER_LIMIT`, `DISCOVER_MIN_SCORE`, `OUTPUT_DIR`.

Generated memos go to `/output/` at repo root (gitignored). The `moggy/output/` source package is not ignored.


### Checking Documentation

- **important:** Always use Context7 when I need library/API documentation, code generation, setup or configuration steps without me having to explicitly ask.

### Git rules
- Never `git push` to `main` without explicit user permission.
- Never `git push --force` on any branch without explicit user permission.
- For all completed work: create a feature branch, push that branch, open a PR. Wait for the user to merge.
