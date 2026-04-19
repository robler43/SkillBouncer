# Estes

**Runtime supply-chain security for agentic AI**

A pre-install auditor and runtime redaction wrapper for third-party skills used by OpenClaw, Antigravity, Claude Code, and watsonx Orchestrate-style agents. Catches the silent credential leaks and tool-output poisoning that flow straight into the model context window.

> **Live prototype:** [estesss.vercel.app](https://estesss.vercel.app/)

---

## The problem

Recent research (April 2026) audited **17,022 publicly available third-party AI agent skills** and found:

- **3.1%** are actively leaking real API keys, OAuth tokens, and passwords during normal execution.
- **73.5%** of leaks come from leftover `print()` / `console.log()` debug statements.
- Agent frameworks automatically capture stdout and inject it directly into the LLM context window.
- Once the secret is in the context, anyone who continues, shares, or exports the chat can extract it with a normal follow-up question.

It's a silent, no-hack-required supply-chain vulnerability that affects every team using agent skills. IBM has flagged this exact risk class for runtime guardrails on platforms like watsonx Orchestrate (which ships with 500+ third-party skills).

## What Estes does

### 1. Pre-Install Auditor (web dashboard)

Drop a `.zip` or paste a public GitHub URL. Estes runs two static passes — no LLM, no telemetry — and returns a single risk score in seconds:

- **Static pass:** regex + entropy detectors for API keys, OAuth tokens, wallet keys, SSH keys, cloud/DB credentials.
- **AST pass (Python):** taint analysis tracking `os.environ` reads and wallet factory calls into `print()`, loggers, and outbound network sinks.

Output: severity-tiered findings, per-finding fix suggestions, JSON export, and a one-click **"Download Fixed"** bundle that applies real safety transformations (literal redaction, blocking unsafe calls) plus an `ESTES_PATCH.md` change log.

### 2. Runtime Wrapper (FastAPI middleware)

A lightweight proxy that runs every tool output through the same regex ruleset before it hits the LLM context. Sub-40 ms per call. Drop-in for Antigravity, Claude Code, OpenClaw. Try it live in the dashboard's **Apply Wrapper** modal.

### 3. Compliance hooks

Every redaction emits a structured ledger entry (`rule`, `severity`, `skill`, `action`) suitable for watsonx.governance-style policy engines and audit trails.

## Architecture

```
User → Antigravity / OpenClaw / Claude Code
            ↓
   Third-party skill runs
            ↓
   Tool output (stdout + result)
            ↓
   Estes wrapper (FastAPI)
            ↓
   Regex + AST detection → redaction + ledger entry
            ↓
   Clean output → LLM context window
```

- **Web dashboard:** single-page FastAPI + vanilla JS frontend (`web/`)
- **Streamlit auditor:** legacy multi-page UI for deep-dive analysis (`app.py`)
- **Runtime wrapper:** standalone FastAPI service (`wrapper.py`)
- **Engine:** `auditor.py` — shared between all three surfaces

## Quick start

### Web dashboard (recommended)

```bash
pip install -r requirements.txt
uvicorn web.server:app --reload --port 5173
# open http://localhost:5173
```

Or just use the live deploy: [estesss.vercel.app](https://estesss.vercel.app/).

### Standalone runtime wrapper

```bash
uvicorn wrapper:app --reload --port 8000
# POST http://localhost:8000/redact  {"text": "..."}
```

### Legacy Streamlit auditor

```bash
streamlit run app.py
```

## Project structure

```
Estes/
├── api/                      # Vercel serverless entrypoint (re-exports web.server.app)
├── web/
│   ├── server.py             # FastAPI dashboard backend
│   ├── index.html            # Single-page dashboard frontend
│   └── README.md             # API + payload schema
├── auditor.py                # Static + AST scanning engine, redact_text()
├── wrapper.py                # Standalone runtime redaction service
├── app.py                    # Legacy Streamlit auditor
├── ui/                       # Streamlit components + per-rule explainers
├── assets/                   # Logo + Streamlit CSS
├── demo/
│   └── weather_tool/         # Deliberately leaky example skill
├── handoff/                  # Project handoff notes
├── vercel.json               # Vercel deploy config
└── requirements.txt
```

## Demo flow

1. Open [estesss.vercel.app](https://estesss.vercel.app/) (or the local server).
2. Drop `demo/weather_tool/` (zip it first) — or any public GitHub repo URL.
3. Watch the risk gauge animate while the scan runs (typically <2s for small skills).
4. Inspect findings: each one shows the offending line, score impact, source pass (static / AST), and a suggested fix.
5. Click **Download Fixed** to get a patched `.zip` with literal secrets redacted, unsafe calls commented out, and a full `ESTES_PATCH.md` change log.
6. Click **Apply Wrapper** to run live tool output through the same redaction engine inside the dashboard.

## Tech stack

- **Web dashboard:** FastAPI + vanilla JS + Tailwind (CDN), single HTML file, dark agentNet-styled UI
- **Engine:** Python AST, regex catalog, entropy heuristics — no LLM dependency
- **Runtime wrapper:** FastAPI + Uvicorn
- **Legacy auditor:** Streamlit
- **Deploy:** Vercel (`@vercel/python` serverless function, stateless download path via base64-embedded zip)

## Roadmap

- Native watsonx.governance API integration for centralized policy and audit logging
- TypeScript/JavaScript AST pass (currently Python-only for taint flow)
- CLI (`estes scan <path>` / `estes start`)
- Signed allowlists and policy-as-code
- Chat Shield warning before sharing or exporting agent conversations

## Built for

- **Hook 'Em Hacks 2026** — *Security in an AI-First World* track (IBM-sponsored)
- Developers using Antigravity, OpenClaw, Claude Code, and agent marketplaces
- Enterprises deploying agentic AI safely and at scale

---

*Built by Robin Ho for Hook 'Em Hacks 2026 · Live at [estesss.vercel.app](https://estesss.vercel.app/)*
