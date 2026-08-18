# HELM — Governed Marketing Orchestration System

Governor-led, star-topology marketing orchestration: ingest ad performance
(Google Ads / Meta via [mureo](https://github.com/logly/mureo), BYOD, or a
SQLite synthetic engine), analyze what works over past data, generate
SEBI-gated creative, propose budget shifts and new campaigns — and execute
only after explicit human approval, with a full audit trail.

## Architecture

- **Governor star relay** (`modules/governor/`) — every hop is a typed
  `HandoffEnvelope`; no agent-to-agent edges; per-hop SQLite checkpoints power
  live progress streaming (SSE).
- **Ads connector** (`modules/ads/`) — the ONLY module allowed to import
  mureo. Data is always labelled honestly: `live` / `byod` / `synthetic` /
  `degraded`. Live writes dispatch through mureo or fail visibly.
- **Analyst** (`modules/ads/analyst.py`) — deterministic what-works ranking,
  decay detection over current-vs-prior periods, budget direction, and new
  campaign drafts (created PAUSED, behind approval).
- **Creative / Compliance / Budget / Execution / Audit** — 4-stage creative
  via the model gateway, deterministic SEBI verifier with loopback, ±25%
  budget cap with conservation, dry-run-first execution engine, append-only
  audit trail.
- **Model gateway** (`services/api/gateway/`) — sole LLM egress (Gemini /
  Anthropic / replay), token ledger, kill switch.
- **Web console** (`apps/web/`) — React SPA: seven agent workspaces, live
  SSE-driven star relay with per-hop timers, HITL approval gate.

## Quick start

```bash
python -m venv .venv
.venv/Scripts/pip install -r requirements.txt   # see "External deps" first
cp .env.example .env                            # add your keys
cd apps/web && npm install && npm run build && cd ../..
.venv/Scripts/python scripts/serve.py           # http://127.0.0.1:8000
```

### External deps

`requirements.txt` installs mureo from a local clone. Fetch it first:

```bash
git clone --depth 1 --branch v0.10.47 https://github.com/logly/mureo external/mureo
```

### Tests

```bash
.venv/Scripts/python -m pytest
```

The suite forces replay mode (no live LLM calls, no ad-platform traffic).

## Platform connections

Dev setup uses Google Cloud Console OAuth credentials + a Google Ads
developer token, and a Meta Graph API token — entered via the console's
Connections panel or `POST /api/connections/{google,meta}`. Credentials live
in server-side custody (`HelmSecretStore`); `~/.mureo/` is never touched.
`HELM_ADS_DRY_RUN=true` is the default — live writes require flipping it
deliberately.
