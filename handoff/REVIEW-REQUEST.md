# Review Request — Step 1
*Written by Builder. Read by Reviewer.*

Ready for Review: YES

---

## What Was Built

Full implementation of the Step 1 auditor module per `handoff/auditor_design.md`, staged at `handoff/auditor.py` (does NOT yet replace the running root `auditor.py` — Architect / Project Owner must move it after sign-off).

Highlights:
- Public API: `scan_skill(source, *, llm=True, timeout_s=30, max_bytes=5MB) -> ScanReport` accepts a local file, directory, `.zip`, or public GitHub URL (including `/tree/<branch>/<subpath>` form).
- Three detection passes feeding one `ScanReport`: Pass A (regex + Shannon entropy + `# skillbouncer: ignore` directive), Pass B (Python AST visitor with env-var symbol table tracking), Pass C (Anthropic Claude Haiku or xAI Grok semantic check, fully optional).
- `_safe_extract` rejects path traversal, absolute paths, symlinks, oversized entries, and aborts at `max_bytes` (closes KG-6).
- Risk score formula: `min(100, 40·high + 12·warning + 3·info)` with `Safe` / `Warning` / `High Risk` bands (closes KG-5).
- Backwards compatible: `SECRET_PATTERNS`, `scan_text`, `scan_path`, `redact_text` preserved with same signatures so `wrapper.py` and `app.py` keep working unchanged.
- LLM pass is degradable: with no API key (or `SKILLBOUNCER_LLM_PROVIDER=off`), the pass writes one warning string and returns; `report.llm_used = False`. Never raises.

## Files Changed

| File | Lines | Change |
|---|---|---|
| `handoff/auditor.py` | 1-870 | New (staged). Full Step 1 implementation. |
| `handoff/BUILD-LOG.md` | full rewrite | Step 1 entry, KG-1/2/5/6/7 marked addressed, KG-8 added (demo SKILL.md self-flagging unresolved). |
| `handoff/REVIEW-REQUEST.md` | this file | Step 1 review request. |

Detailed line ranges within `handoff/auditor.py`:

| Section | Lines |
|---|---|
| Imports + dotenv | 30-52 |
| Constants (suffixes, skip dirs, manifest names, ignore directive, allowlists) | 55-93 |
| `SECRET_PATTERNS` + `_STATIC_RULE_META` (Phase 0 ruleset preserved + rule IDs) | 96-148 |
| Data model: `Finding`, `SkillManifest`, `ScanReport` (+ `to_dict` / `to_json`) | 151-205 |
| Pass A — `_scan_static` (regex + entropy + ignore) | 208-281 |
| Pass B — AST helpers (`_flatten_attr`, `_LeakVisitor`, `_scan_ast`) | 284-453 |
| Pass C — LLM (`_call_anthropic`, `_call_xai`, `_parse_llm_json`, `_llm_semantic_check`) | 456-606 |
| Source resolution (`_parse_github_url`, `_fetch_github_zip`, `_safe_extract`, `_resolve_source`) | 609-771 |
| Discovery (`_discover_manifest`, `_discover_files`) | 774-833 |
| Aggregation (`_compute_score`, `_compute_severity`, `_rollup_suggested_fix`, `_dedupe`) | 836-878 |
| Public API (`scan_skill`, `scan_path`, `redact_text`, `__all__`) | 881-end |

## Smoke Tests Run

All passed:

1. `scan_skill('demo/weather_tool', llm=False)` → severity=`High Risk`, score=100, files=2, **3 high AST findings** (`SB-PRINT-ENV-01` ×2 + `SB-LOG-ENV-01`) + bonus `SB-NET-PHONEHOME-01` warning + 6 static findings. Symbol table correctly resolves `API_KEY = os.environ.get(...)` then `print(f"...{API_KEY}...")`.
2. Clean fixture (harmless skill) → severity=`Safe`, score=0, 0 findings.
3. Zip with `../../etc/passwd_pwned` entry → entry rejected with warning, no escape, no findings.
4. File with `api_key = "abcdef1234567890XYZ"  # skillbouncer: ignore` → 0 findings (KG-7 closed).
5. `report.to_json()` → 5,808-char JSON, round-trips cleanly through `json.loads`.

## Open Questions

1. **Swap-in instruction**. The brief said write to `handoff/auditor.py`. The running code in the repo root is unchanged. After Reviewer signs off, the activation step is:

   ```bash
   cd /Users/robinhoesli/Desktop/projects/SkillBouncer
   mv handoff/auditor.py auditor.py
   ```

   `wrapper.py` and `app.py` need no changes — the new module preserves every Phase 0 export.

2. **LLM default unresolved.** Architect's design left this as an open question for Project Owner. Builder defaulted `scan_skill(llm=True)` per Architect's recommendation; `scan_path()` (compatibility shim used by Streamlit + FastAPI) stays `llm=False`. Confirm or reverse before Step 2.

3. **Demo `SKILL.md` self-flagging (KG-8).** The new ignore directive can fix this if added to the SKILL.md, but Step 1 deliberately did not modify the demo. Project Owner: do you want the demo SKILL.md left noisy (so the score reads 100 for the demo), or cleaned with `# skillbouncer: ignore` markers (so the score reads ~60 from the actual code)?

4. **Bonus AST rule fired on demo**. `SB-NET-PHONEHOME-01` (warning) fires on `requests.get("https://api.weatherapi.com/...")` because the function also touches env vars. This is correct per spec but wasn't called out in the demo brief. Acceptable?

5. **Tests**. KG-4 still open — the smoke tests above are ad-hoc. Recommend adding `pytest` + `tests/fixtures/` (zip-bomb, traversal, clean, leaky weather, missing manifest) as Step 1.5. Should this block Step 1 deploy?

## Known Gaps Logged

- KG-1 — Entropy: ADDRESSED in Step 1.
- KG-2 — AST: ADDRESSED in Step 1.
- KG-3 — Antigravity hook: still open (Step 2).
- KG-4 — Automated tests: still open (proposed Step 1.5).
- KG-5 — Risk score formula: ADDRESSED in Step 1.
- KG-6 — Zip-bomb / path-traversal: ADDRESSED in Step 1.
- KG-7 — `# skillbouncer: ignore`: ADDRESSED in Step 1.
- KG-8 — Demo SKILL.md still self-flags (new): pending Project Owner call (see Open Question 3).
