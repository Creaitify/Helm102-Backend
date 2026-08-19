# Project: HELM02 Governed Marketing Orchestration System

## Architecture
HELM is a governed marketing operations control plane. A Governor-led star relay DAG drives
six hops; a model gateway fronts Gemini/Anthropic with a cost ledger; a chat-first React
console lets operators address the whole pipeline or any single specialist directly. Campaign
data comes from live Google/Meta REST clients, coherent SQLite synthetic datasets, or an
imported CSV — always labelled honestly. SEBI compliance is deterministic, budget moves are
policy-bounded, and nothing dispatches without human approval.

### System Topology (Star Relay DAG)
- **Central Hub**: `GovernorOrchestrator` (`modules/governor/orchestrator.py`)
- **Hop 0**: User Ingress (`INGEST_OBJECTIVE`)
- **Hop 1**: Ad-Ops Analyst (`FETCH_AND_ANALYZE_CAMPAIGNS` via Mureo / SQLite / BYOD)
- **Hop 2**: Creative Studio (`GENERATE_CREATIVE_PACKAGE` via Gemini 2.5 Gateway)
- **Hop 3**: SEBI Compliance Shield (`VERIFY_SEBI_REGULATORY` with deterministic rules + loopback retry)
- **Hop 4**: Budget Optimizer (`PROPOSE_BUDGET_REALLOCATION` with ±25% bounds & conservation)
- **Hop 5**: Governor Synthesis & Human Approver Gate (`SUBMIT_PROPOSAL_FOR_APPROVAL`, pauses in `pending_approval`)
- **Hop 6**: Execution Engine (`execute_proposal` to Meta/Google Ads via dry-run/live upon operator approval)

---

## Feature Inventory

| # | Feature | Description | Milestone | Source | Status |
|---|---------|-------------|-----------|--------|:------:|
| 1 | Ingest Marketing Objective | Ingests marketing goals and initiates 6-hop star relay | M1 | Survey | DONE |
| 2 | Handoff Envelope Exchange | Standardized immutable typed message envelope | M1 | Survey | DONE |
| 3 | SQLite State Checkpointing | Durably persists intermediate run state after every hop | M1 | Survey | DONE |
| 4 | Immutable Audit Trail | Append-only SQLite envelope ledger for regulatory audit | M1 | Survey | DONE |
| 5 | Controlled LLM Invocation | Single point of egress for LLM calls with token accounting | M2 | Survey | DONE |
| 6 | Gemini 2.5 Provider Adapter | Native Generative Language API adapter with JSON schema mode | M2 | Survey | DONE |
| 7 | Budget Ledger & Kill Switch | Pre-reserves cost, checks daily ceiling, enforces kill switch | M2 | Survey | DONE |
| 8 | Structured Creative Schema | 4-stage pipeline (Brief -> 9:16 Video Script -> Ad Copy -> Captions) | M2 | Survey | DONE |
| 9 | Multi-Channel Data Ingestion | Ingests campaign snapshots from Mureo, BYOD, or SQLite | M3 | Survey | DONE |
| 10 | Ad-Ops Performance Analytics | Composite scoring, decay detection (CTR drop ≥25%, CPA surge ≥30%) | M3 | Survey | DONE |
| 11 | BYOD CSV / Excel Importer | Ingests custom marketing datasets without OAuth credentials | M3 | Survey | DONE |
| 12 | Coherent SQLite Synthetic Engine | Multi-channel 30-60 day synthetic datasets with realistic decay | M3 | Survey | DONE |
| 13 | Scenario Preset Engine | 4 presets (growth_and_fatigue, scale_winner, sebi_risk, mix) | M3 | Survey | DONE |
| 14 | SEBI Deterministic Verifier | Regulatory rules checking prohibited claims & mandatory disclaimers | M3 | Survey | DONE |
| 15 | Automated Safety Loopback | Re-generates sanitized copy when creative fails compliance | M3 | Survey | DONE |
| 16 | Policy-Bounded Optimizer | Optimizes budget while enforcing ±25% cap & conservation | M3 | Survey | DONE |
| 17 | Human Approval Gate | Pauses run at Hop 5, resumes to Hop 6 only upon human approval | M3 | Survey | DONE |
| 18 | Gated Platform Executor | Dispatches approved changes to Meta & Google Ads with dry-run | M3 | Survey | DONE |
| 19 | Governor HQ Workspace | Mission launcher, preset selector, and live Star Relay DAG | M4 | Survey | DONE |
| 20 | Ad-Ops Workspace | Ingested metrics table, ROAS/CPA scores, decay alerts, BYOD | M4 | Survey | DONE |
| 21 | Creative Studio Workspace | 4-Stage visual breakdown (Brief, 9:16 Script, Ad Copy, Captions) | M4 | Survey | DONE |
| 22 | Compliance Shield Workspace | Interactive copy scanner and regulatory audit verdict | M4 | Survey | DONE |
| 23 | Budget Optimizer Workspace | Daily budget shifts table, ±25% boundaries, conservation proof | M4 | Survey | DONE |
| 24 | Execution Engine Workspace | Human signoff interface, dry-run JSON payload preview, receipts | M4 | Survey | DONE |
| 25 | Immutable Audit Workspace | Chronological timeline of cryptographic envelopes with JSON viewer | M4 | Survey | DONE |
| 26 | Non-Vanishing State Store | Central React context synchronizing state to localStorage | M4 | Survey | DONE |
| 27 | Google Stitch Design Theme | White & Royal Blue palette (#F8FAFC, #FFFFFF, #E2E8F0, #2563EB) | M4 | Survey | DONE |
| 28 | Tier 1 Unit & Feature Tests | 32 automated unit tests across API, DB, Gateway, BYOD, Ads | M5 | Survey | DONE |
| 29 | Tier 2 Boundary Tests | 22 boundary tests (clamp, conservation, SEBI blocks, kill switch) | M5 | Survey | DONE |
| 30 | Tier 3 Cross-Feature Tests | 12 integration tests (Full Star Relay, Checkpointer, HITL gate) | M5 | Survey | DONE |
| 31 | Tier 4 Real-World Tests | 9 realistic scenarios (Decay signals, Winner scale, Provider switch) | M5 | Survey | DONE |
| 32 | Forensic Integrity Audit | Static analysis, execution validation, and anti-cheating verification | M5 | Survey | DONE |
| 33 | Direct Single-Agent Invocation | Address one specialist without paying for the full six-hop relay | M6 | Request | DONE |
| 34 | Agent Display Grammar | Agents emit typed blocks; one renderer covers every agent | M6 | Request | DONE |
| 35 | Conversation Persistence | SQLite-backed threads; reopening replays stored render payloads | M6 | Request | DONE |
| 36 | Unified Chat Endpoint | One prompt in, a persisted two-sided exchange out | M6 | Request | DONE |
| 37 | Analysis Report Engine | Point-in-time account documents with Markdown export | M6 | Request | DONE |
| 38 | Google Ads REST Client | Direct API client (OAuth refresh, GAQL searchStream, budget mutate) | M6 | Request | DONE |
| 39 | Meta Marketing REST Client | Direct Graph API client for insights and budget writes | M6 | Request | DONE |
| 40 | Live Connection Verification | Real handshake probe, not merely "credentials present" | M6 | Request | DONE |
| 41 | Stitch Control-Plane Console | Chat-first shell: nav rail, thread, agent status rail, composer | M6 | Request | DONE |
| 42 | Frontend Render Test Suite | Mounts the real shell against a stubbed API; covers every block type | M6 | Request | DONE |

---

## Milestones

| # | Name | Scope | Dependencies | Status | Key Outputs |
|---|------|-------|-------------|:------:|-------------|
| 1 | Core Data Contracts & Checkpointer | Typed Envelopes, Star Relay Engine, SQLite Checkpointer, Audit Trail | None | DONE | `modules/governor/`, `modules/audit/`, `governor_checkpoints.sqlite` |
| 2 | Gemini 2.5 Gateway & Schemas | Gateway Service, Gemini 2.5 Adapter, Micro-dollar Ledger, 4-Stage Creative Schema | M1 | DONE | `services/api/gateway/`, `modules/creative/`, 10 gateway unit tests |
| 3 | Synthetic Engine, SEBI & Budget | SQLite Synthetic Engine, Ad-Ops Analyst, SEBI Verifier, Budget Optimizer, HITL Gate | M1, M2 | DONE | `services/api/db/`, `modules/compliance/`, `modules/budget/`, `modules/ads/` |
| 4 | Persistent React Workspaces | 7 Workspaces, Non-Vanishing Store, Google Stitch Theme, Vite Build | M1, M2, M3 | DONE | `apps/web/src/components/workspaces/`, `HelmStore.jsx`, `styles.css` |
| 5 | Full Integration & Test Pass | 4-Tier Test Suite (168/168 passing), Vite Bundle Build, Forensic Integrity Audit | M1, M2, M3, M4 | DONE | 168 passed tests in 4.07s, clean Vite bundle, CLEAN audit verdict |
| 6 | Control Plane & Live Data | Direct agents, chat/conversation persistence, reports, real Google/Meta clients, console rewrite | M1-M5 | DONE | 210 backend + 13 frontend tests passing; `apps/web/src/`, `services/api/{agents,chat,conversations,reports}.py`, `modules/ads/{google,meta}_ads_client.py` |

---

## Interface Contracts

### Governor ↔ Workers (Typed Envelopes)
- `HandoffEnvelope(hop_index: int, source: str, target: str, action: str, status: EnvelopeStatus, payload: dict, rationale: str, error: str | None, timestamp: str)`
- `EnvelopeStatus`: `SUCCESS`, `DEGRADED`, `FAILED`, `NEEDS_REVISION`

### Gateway ↔ Models (CompletionRequest / CompletionResponse)
- `CompletionRequest(task_kind: TaskKind, messages: list[Message], model: ModelRef | None, max_tokens: int | None, temperature: float | None, response_schema: dict | None)`
- `CompletionResponse(content: str, parsed_json: dict | None, usage: Usage, model: str, finish_reason: str)`
- `Usage(prompt_tokens: int, completion_tokens: int, total_tokens: int, cost_microdollars: int)`

### Checkpointer ↔ SQLite
- `GovernorCheckpointer.save_checkpoint(run_id: str, status: str, hop_index: int, state_json: str)`
- `GovernorCheckpointer.load_checkpoint(run_id: str) -> dict | None`

### Compliance ↔ Governor / Creative
- `SEBIComplianceVerifier.verify_text(text: str) -> ComplianceVerdict`
- `SEBIComplianceVerifier.verify_package(package: CreativePackage) -> ComplianceVerdict`
- `ComplianceVerdict(status: ComplianceStatus, passed: bool, violations: list[Violation], recommendations: list[str])`

---

## Code Layout

```text
HELM/
├── apps/web/                              # React 18 + Vite + Tailwind console
│   ├── src/
│   │   ├── components/
│   │   │   ├── blocks/BlockRenderer.jsx   # Renders the agent display grammar
│   │   │   ├── Sidebar.jsx                # Dark nav rail: history + resources
│   │   │   ├── TopBar.jsx                 # Search, grounding, model selector
│   │   │   ├── AgentRail.jsx              # Agent status + approval gate
│   │   │   ├── MessageThread.jsx          # Conversation turns and sources
│   │   │   ├── Composer.jsx               # Mode selector + prompt input
│   │   │   └── ui.jsx                     # Chips, buttons, INR formatting
│   │   ├── screens/                       # Chat, Reports, Settings,
│   │   │                                  #   DataSources, PromptLibrary, Audit
│   │   ├── __tests__/app.test.jsx         # Render smoke tests (vitest + jsdom)
│   │   ├── store.jsx                      # Single source of truth
│   │   ├── api.js                         # REST wrapper with honest errors
│   │   └── styles.css                     # Tailwind layers + design tokens
│   └── tailwind.config.js                 # Stitch "Autonomous Control Plane" tokens
│
├── services/api/
│   ├── main.py                            # Wiring, health, stats, connection verify
│   ├── agents.py                          # Direct single-agent invocation
│   ├── chat.py                            # Unified send-path
│   ├── conversations.py                   # Thread + message persistence
│   ├── reports.py                         # Report generation & Markdown export
│   ├── gateway/                           # Model gateway, adapters, cost ledger
│   ├── db/synthetic_sqlite.py             # Coherent synthetic datasets
│   ├── knowledge/citations.py             # SEBI citation grounding
│   └── auth/                              # OAuth flow + server-side secret store
│
├── modules/
│   ├── governor/                          # Star-relay orchestrator, checkpointer
│   ├── ads/
│   │   ├── connector.py                   # Platform protocol + honest labelling
│   │   ├── google_ads_client.py           # Direct Google Ads REST client
│   │   ├── meta_ads_client.py             # Direct Meta Graph client
│   │   ├── analyst.py                     # Scoring, decay detection, synthesis
│   │   ├── byod_importer.py               # CSV / Excel ingestion
│   │   └── gaql.py                        # GAQL builders and parsers
│   ├── creative/                          # 4-stage creative pipeline
│   ├── compliance/                        # Deterministic SEBI verifier
│   ├── budget/                            # Policy-bounded optimizer (±25%)
│   ├── execution/                         # Gated platform executor
│   └── audit/                             # Append-only envelope trail
│
└── scripts/
    ├── serve.py                           # API server
    └── dev.py                             # Build console if stale, then serve
```
