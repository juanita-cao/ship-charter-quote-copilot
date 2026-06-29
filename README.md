# Ship Charter Quote Copilot

[![CI](https://github.com/juanita-cao/ship-charter-quote-copilot/actions/workflows/ci.yml/badge.svg)](https://github.com/juanita-cao/ship-charter-quote-copilot/actions/workflows/ci.yml)
![Python 3.11+](https://img.shields.io/badge/Python-3.11%2B-blue)
![Streamlit](https://img.shields.io/badge/UI-Streamlit-red)
![Tests](https://img.shields.io/badge/tests-116%20passing-brightgreen)

**[Live demo →](https://ship-charter-quote-copilot.streamlit.app/)**

A decision-support tool for a ship charterer (an "Operator," who charters a vessel **in** from a shipowner and carries cargo **for** a cargo owner). Given one voyage's details, it computes whether the deal is worth taking (GO/NO-GO), what rate to quote the cargo owner to hit a target margin, how sensitive the deal is to common risks, and lets the user save a confirmed quote for later reference.

**Every number on screen is a fast, synchronous, pure function — no spinners, no job queue.** Edit any input and the whole decision recomputes live.

---

## Demo Preview

![Workspace preview](docs/assets/dashboard_preview.png?v=2)

---

## What this demonstrates

- **Two decoupled decision points sharing one computation core.** "Should I take this voyage" (a company-wide profit-margin threshold) and "what should I quote the cargo owner" (a personal target-TCE reverse-calculation) are independent questions that happen to read from the same TCE calculation — modeled as two separate decision gates, not one over-loaded rule.
- **A bidirectional negotiation sandbox.** Edit Target TCE or Freight Rate and the other recalculates instantly, reusing the same decision logic the main panel uses — not a separate, drifting copy of the rule.
- **Risk sensitivity, not just a point estimate.** A 5-row scenario table (port cost, bunker price, schedule margin, freight rate, each independently adjustable) shows how much room the deal has to spare, not just whether it currently clears the bar.
- **A deliberately decoupled persistence boundary.** Live recompute never touches the database; only an explicit "Save Quote" click does, and a database connection is optional — the app runs and exports CSV with or without one.
- **Design-before-code workflow.** The two documents in [`docs/`](docs/) were written before the corresponding implementation, each capturing the formula corrections found along the way as dated decision records rather than silently rewriting history.

---

## Architecture

```
Input form ──► E1 collect & validate ──► E2 TCE calculation ──┬──► D1 GO/NO-GO gate
                                                                ├──► D2 reverse quote (target TCE → rate)
                                                                └──► E3 risk scenarios (5 rows)
                                                                          │
                                                                          ▼
                                                              E4 save (optional DB write)
```

Design documents:
- [`docs/design_backend.md`](docs/design_backend.md) — pipeline table, data contracts, ADRs
- [`docs/design_frontend.md`](docs/design_frontend.md) — state machine, ViewModel, screen flow

## Tech stack

| Layer | Tools |
|---|---|
| Backend | Python 3.11, Pydantic v2 |
| Data (optional) | Postgres, psycopg3 — app runs without it (soft-fail save) |
| Frontend | Streamlit, ViewModel-pattern state management |
| Quality / CI | pytest (116 tests), ruff, GitHub Actions |
| Hosting | Streamlit Community Cloud |

Engineering approach (contract-first workflow):

1. Define input/output schemas before implementing pipeline logic.
2. Separate calculation execution, validation checks, and decision interpretation into distinct stages.
3. Preserve every formula correction as a dated, reasoned decision record instead of silently overwriting the previous version.
4. Use explicit validation gates before presenting results as decision support.
5. Keep persistence decoupled from the live-recompute loop — only an explicit user action writes to storage, and that write is allowed to fail without breaking anything already on screen.
6. Keep the UI layer separate from the calculation pipeline through a ViewModel-style interface, so the frontend never touches raw pipeline state.

---

## Quickstart

```bash
git clone https://github.com/juanita-cao/ship-charter-quote-copilot.git
cd ship-charter-quote-copilot
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

# run the test suite (116 tests)
pytest -q

# lint
ruff check .

# launch the UI
streamlit run src/frontend/app_streamlit.py

# or run the full pipeline from the command line, no UI
python -m scripts.run_demo
```

Requires Python 3.11+ (the codebase uses `X | None` union syntax evaluated at runtime by Pydantic). A Postgres connection is optional — without `DATABASE_URL` set, "Save Quote" simply skips the database write and the CSV export still works.

CI runs the same lint + test commands on every push — see [`.github/workflows/ci.yml`](.github/workflows/ci.yml).

---

## Data note

The pre-filled sample voyage and every test fixture in this repo use round-number, illustrative figures — not a real client's confidential rates, routes, or cargo. The calculation logic itself (TCE formula, decision rules, reverse-quote math) is real and fully tested; only the displayed example numbers are synthetic.

---

## Project structure

```
docs/             design documents — read before the corresponding code was written
src/backend/      calculation pipeline, schemas, decision gates, optional Postgres access
src/frontend/     Streamlit UI, ViewModel layer, session-state machine
scripts/          CLI smoke-test entry point (no UI, no mocks)
tests/            116 tests covering every pipeline stage and the frontend state machine
```

---

## Current Scope

Implemented:
- TCE calculation from full voyage/cost inputs (ballast/laden legs, bunker, port costs)
- Binary GO/NO-GO decision gate with a configurable profit-margin threshold
- Reverse quote: solve for the minimum freight rate to hit a target TCE
- Bidirectional rate↔TCE negotiation sandbox with an independent shipowner-ask override
- 5-row risk scenario table with independently adjustable deltas
- Quote persistence with graceful degradation when no database is configured
- CSV export of any computed quote
- Streamlit UI: Welcome screen, Run gate for first-time clarity, Reset All for a clean slate
- CI: lint + 116 tests on every push

Not implemented:
- Real-time distance/bunker-price/market-benchmark APIs — all manual entry by design, not a placeholder
- Freight-rate market-benchmark engine (mirrors the TCE benchmark pattern, deferred)
- Multi-ship comparison or negotiation round history
- Multi-user authentication

Per-step implementation status: `docs/design_backend.md` and `docs/design_frontend.md`, each under "Task list and implementation status."
