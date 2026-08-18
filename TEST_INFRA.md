# E2E Test Infra: HELM02 Governed Marketing Orchestration System

## Test Philosophy
- Requirement-driven, opaque-box testing against core contracts and user goals.
- 4-Tier verification methodology: Feature/Unit (Tier 1), Boundary & Corner Cases (Tier 2), Cross-Feature Combinations (Tier 3), and Real-World Application Workloads (Tier 4).
- 75 automated tests executed via Pytest + Vite frontend production build check + Forensic integrity verification.

## Feature Inventory & Test Mapping

| # | Feature Area | Tier 1 (Unit) | Tier 2 (Boundary) | Tier 3 (Cross-Feature) | Tier 4 (Real-World) | Total Tests |
|---|--------------|:-------------:|:-----------------:|:----------------------:|:-------------------:|:-----------:|
| 1 | API Endpoints & Health | 4 | 2 | 2 | 2 | 10 |
| 2 | Knowledge & Citations | 4 | 3 | 2 | 0 | 9 |
| 3 | DB & Repository | 4 | 1 | 1 | 0 | 6 |
| 4 | Model Gateway & Gemini 2.5 | 4 | 3 | 1 | 2 | 10 |
| 5 | Secret Store & Credentials | 4 | 1 | 0 | 1 | 6 |
| 6 | Synthetic SQLite Engine | 3 | 2 | 1 | 2 | 8 |
| 7 | Ad-Ops & Connectors | 3 | 2 | 1 | 2 | 8 |
| 8 | BYOD CSV / Excel Parser | 3 | 4 | 1 | 1 | 9 |
| 9 | Governor Star Relay & Checkpoint | 1 | 0 | 4 | 0 | 5 |
| 10| SEBI Compliance Verifier | 1 | 3 | 0 | 0 | 4 |
| 11| Budget Policy Optimizer | 1 | 4 | 0 | 0 | 5 |
| **Total** | | **32** | **22** | **12** | **9** | **75** |

## Test Architecture
- **Test Runner**: `.venv\Scripts\pytest -v modules/ services/`
- **Frontend Bundle Verifier**: `npm run build` in `apps/web/`
- **Target Pass Semantics**: 75 passed, 0 failed, 0 errors, exit code 0.
- **Vite Build Semantics**: `vite v6.4.3` builds `dist/` cleanly, exit code 0.

## Tier Breakdown & Scenarios
- **Tier 1 (Feature Coverage, 32 tests)**: Basic happy paths for health, connections, BYOD samples, citations index, database repositories, gateway replay, synthetic snapshot loading, connector execution.
- **Tier 2 (Boundary & Corner Cases, 22 tests)**: Zero conversions/impressions safe division, currency stripping, malformed CSV error reporting, budget ±25% clamps, budget conservation trimming, SEBI hard blocks, missing disclaimers, character offset exact slicing, token budget ceilings, kill switch trips.
- **Tier 3 (Cross-Feature Combinations, 12 tests)**: Full 6-hop Star Relay execution, per-hop SQLite checkpoint saving, immutable audit ledger writes, human approval pause & resumption, background asynchronous polling, multi-factor citation grounding, multi-sheet Excel parsing.
- **Tier 4 (Real-World Application Scenarios, 9 tests)**: 60-day coherent CTR decay and CPA surge detection, automated campaign draft generation for winners, Finnovate multi-artifact roundtrip export/import, dynamic Gemini 2.5/Anthropic model switching, secret masking in API responses.
