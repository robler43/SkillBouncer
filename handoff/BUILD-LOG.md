# Build Log
*Owned by Architect. Updated by Builder after each step.*

---

## Current Status

**Active step:** 1 — Auditor module rewrite (`handoff/auditor.py` staged for review)
**Last cleared:** Step 0 — 2026-04-18
**Pending deploy:** NO (awaiting REVIEWER on Step 1)

---

## Step History

### Step 1 — Auditor module rewrite — READY FOR REVIEW
*Date: 2026-04-18*

Files changed:
- `handoff/auditor.py` — full implementation per `handoff/auditor_design.md` (staged; does NOT replace root `auditor.py` until REVIEWER signs off)
- `handoff/BUILD-LOG.md` — this update
- `handoff/REVIEW-REQUEST.md` — populated for REVIEWER

Decisions made:
- **Output location**: Per Project Owner's instruction, the implementation lives at `handoff/auditor.py`, not at the repo root. The running root `auditor.py` is unchanged. Architect / Project Owner must `mv handoff/auditor.py auditor.py` after review to activate it.
- **LLM default unresolved**: Architect's design left the `llm` default as an open question for Project Owner. Builder shipped `llm=True` (Architect's recommendation) for `scan_skill`, and kept `scan_path()` as `llm=False` so the existing Streamlit UI and FastAPI `/scan` endpoint stay fast. Override with env var `SKILLBOUNCER_LLM_PROVIDER=off`.
- **Backwards compatibility**: `SECRET_PATTERNS`, `scan_text`, `scan_path`, `redact_text` are preserved with the same signatures. `wrapper.py` and `app.py` need no changes for the swap-in.
- **Bonus AST rule fired**: Demo weather_tool now also triggers `SB-NET-PHONEHOME-01` (warning) because `requests.get("https://api.weatherapi.com/...")` is reached from a function that touches `os.environ`-bound locals. This wasn't requested in the demo brief but matches the spec's reachability rule. Score caps at 100 either way.

Smoke-test results (from `handoff/auditor.py` against `demo/weather_tool/`):
- severity=`High Risk`, score=100
- 9 high + 1 warning total (6 static from `SKILL.md` quoting leak code + 3 high AST from `weather.py` + 1 phone-home warning)
- AST correctly resolves `API_KEY = os.environ.get(...)` then `print(f"...{API_KEY}...")` via the env-var symbol table
- Path-traversal zip rejected with warning, no escape
- `# skillbouncer: ignore` suppresses static findings on the marked line (closes KG-7)
- `report.to_json()` round-trips cleanly through `json.loads`
- Clean fixture (no leaks) returns severity=`Safe`, score=0

Reviewer findings: pending
Deploy: pending

---

## Known Gaps
*Logged here instead of fixed. Addressed in a future step.*

- **KG-1** — Shannon entropy: ADDRESSED in Step 1 (`SB-ENTROPY-01` warning on quoted literals ≥ 20 chars with entropy ≥ 4.5 bits/char).
- **KG-2** — Python AST pass: ADDRESSED in Step 1 (seven rules: `SB-PRINT-ENV-01`, `SB-LOG-ENV-01`, `SB-EXEC-01`, `SB-SUBPROC-SHELL-01`, `SB-OS-SYSTEM-01`, `SB-FILE-SECRET-READ-01`, `SB-NET-PHONEHOME-01`).
- **KG-3** — Wrapper has no actual Antigravity integration. `/redact` is a manual POST endpoint. Still open. Plan: Step 2 spike.
- **KG-4** — No automated tests. Builder ran ad-hoc smoke tests but `pytest` + `tests/fixtures/` is not set up. Still open. Plan: Step 1.5 or as part of Step 2.
- **KG-5** — Risk score formula: ADDRESSED in Step 1 (`min(100, 40·high + 12·warning + 3·info)` with `Safe` / `Warning` / `High Risk` bands).
- **KG-6** — Zip-bomb / path-traversal: ADDRESSED in Step 1 (`_safe_extract` rejects absolute paths, `..`, symlinks, oversized entries, and aborts at `max_bytes`).
- **KG-7** — `# skillbouncer: ignore` directive: ADDRESSED in Step 1 (line-level suppression in Pass A; supports `#` and `//` comment styles).
- **KG-8** — `demo/weather_tool/SKILL.md` still inflates the score because it quotes the leak code verbatim. The ignore directive can suppress this if added to the SKILL.md, but Step 1 did not modify the demo. Still open as documentation polish.

---

## Architecture Decisions
*Locked decisions that cannot be changed without breaking the system.*

- **AD-1 (2026-04-18)** — Two-component architecture: Auditor (pre-flight static scanner) and Runtime Wrapper (in-flight redacting proxy). Both consume a shared detection ruleset.
- **AD-2 (2026-04-18)** — Auditor frontend is Streamlit; Wrapper service is FastAPI on Uvicorn.
- **AD-3 (2026-04-18)** — Primary integration target is Antigravity using the Claude model. Other agent frameworks are out of scope until Phase 2+.
- **AD-4 (2026-04-18)** — Detection rules are the single source of truth shared between Auditor and Wrapper. Any new rule must work in both contexts. (Step 1 honors this: `SECRET_PATTERNS` and `redact_text` are preserved, AST findings are auditor-only by design.)
- **AD-5 (2026-04-18)** — Python 3.11+ is the minimum supported runtime. Dependencies are pinned with exact versions in `requirements.txt`.
- **AD-6 (2026-04-18)** — `app.py` is the canonical user-facing entry point (`streamlit run app.py`). `auditor.py` is a pure library with no Streamlit dependency.
- **AD-7 (2026-04-18 — proposed by Reviewer, not yet ratified)** — `demo/` directory and clearly-fake credential placeholders in demo skills are legitimate first-class artifacts, superseding the original Step 0 brief flags. Architect to ratify in next round.
