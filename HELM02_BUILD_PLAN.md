# HELM02 — Build Plan

**Decision date:** 2026-08-17
**Status:** approved direction, not yet started
**Supersedes:** the "project scaffold first" ordering in `AGENTS.md`

---

## 0. The decision in one paragraph

HELM02 is the **replacement product**, not a demo. It is a new repository with clean module
boundaries, into which we (a) **port** the load-bearing Python core of HELM — the Governor star
relay, the typed envelopes, the checkpointed HITL gate, the policy engine, the SEBI compliance
verifier and the model gateway — and (b) **depend on** `mureo==0.10.47` as the ad-platform
connector layer rather than building or vendoring one. HELM's Next.js console does not come
across; a new four-screen UI replaces it. `simplicio-loop-marketing` contributes its pipeline
stage taxonomy as a schema shape and **no code**. Net: ~9,600 lines ported, ~9,200 lines
abandoned, ~107,000 lines inherited as a pinned dependency we do not maintain.

---

## 1. Why not the other options

### 1.1 Why not keep building HELM in place

`docs/reports/HELM_STATE_AND_DIRECTION_2026-08-17.md` found six duplicated subsystems — four copies
of the campaign table, three "not real" modes, two ad-platform integrations in two languages, two
run stores, two execution paths. Every one of those is a merge artefact of building the platform
before the loop. They can be deleted in place (Phase A of that report), but the *shape* that
produced them — a 14-page console built from a mockup, a worker inventing its own data layer
because Phase 2 endpoints never landed — is structural. A new repo with the module boundaries in
`AGENTS.md` makes the split-brain unrepresentable rather than merely absent.

### 1.2 Why not rewrite mureo into HELM02

`logly/mureo` is 107,562 lines of Python against 143,677 lines of tests across 364 test files. It
ships the official `google-ads` (28–30) and `facebook-business` (20–22) SDKs, and released v0.10.47
on 2026-08-17. Absorbing that as source means owning 107k lines of unfamiliar code and losing
upstream fixes for every Google Ads API version bump. As a pinned dependency it costs one line in
`requirements.txt`.

### 1.3 Why simplicio-loop-marketing contributes no code

15,009 lines, first commit 2026-05-08, last commit 2026-08-04 — three months old, two weeks stale.
31 of 140 commits are authored by "Claude"; 19 root-level markdown files total 3,407 lines against
15k of code, and the repo ships a `claims:audit` script to check its own README against reality.
Two runtime dependencies means all nine publishing integrations are hand-rolled. Decisive
objection: its whole selling point is an env-switchable LLM/image/video provider router. That
router bypasses our token ledger, daily budget ceiling and kill switch. **We take the
`brief → script → creative → caption` stage names as the shape of the Creative agent's output
schema, and nothing else.**

---

## 2. Verified facts this plan rests on

Checked in a clean Python 3.11 venv on 2026-08-17:

| Claim | Result |
|---|---|
| `pip install mureo==0.10.47` | ✅ resolves and installs clean |
| `mureo.google_ads.client` importable | ✅ exposes `GoogleAdsApiClient`, `map_campaign`, `map_ad_group`, `map_performance_report` |
| `mureo.google_ads._gaql_validator` importable | ✅ |
| `mureo.meta_ads`, `mureo.byod`, `mureo.rollback`, `mureo.analysis` importable | ✅ |
| Credential source injectable | ✅ `mureo.core.secret_store` defines a `runtime_checkable` **`SecretStore` Protocol**; `FilesystemSecretStore(path: Path \| None = None)` is just the default implementation |

That last row is the one that makes this plan possible. mureo is marketed as "local-first" and
defaults to `~/.mureo/credentials.json`, but the store is a Protocol — we implement
`HelmSecretStore` against server-side custody and mureo never touches the operator's home
directory.

### 2.1 Open compatibility item

mureo declares `requires-python = ">=3.10"` but its trove classifiers stop at **3.12**. HELM's
`api/` currently runs **3.13/3.14** (`.mypy_cache/3.13`, `__pycache__/*.cpython-314.pyc`). Resolve
before Phase 2: either pin HELM02 to 3.12, or install mureo and run its Google/Meta paths on 3.13+
and confirm the `google-ads` protobuf stack behaves. Do not assume.

---

## 3. Module map

```text
helm02/
  apps/
    web/                  NEW — four screens only: Run, Proposal, Approvals, Audit
  services/
    api/                  PORT from HELM api/ — gateway, identity spine, run store
  modules/
    governor/             PORT from HELM workers/ — star graph, envelopes, checkpointer, HITL
    ads/                  NEW THIN WRAPPER over mureo — the only place mureo is imported
    creative/             NEW — schema shaped by simplicio's stage taxonomy
    compliance/           PORT from HELM — deterministic SEBI verifier
    budget/               PORT from HELM — apply_policy() ±25% cap + conservation
    execution/            NEW — Governor dispatches here; wraps mureo write paths
    audit/                PORT from HELM — append-only envelope log
  docs/
    AGENTS.md  demo.md  HELM02_BUILD_PLAN.md  TASK_LOG.md
```

### 3.1 The one rule that keeps this clean

**`modules/ads/` is the only module permitted to `import mureo`.** Everything upstream talks to a
local `Connector` protocol:

```python
class Connector(Protocol):
    def fetch_campaigns(self) -> CampaignSnapshot: ...
    def apply_budget(self, shift: BudgetShift) -> ExecutionResult: ...
    def deploy_creative(self, variant: CreativeVariant) -> ExecutionResult: ...
```

If mureo ever has to be replaced — bus factor is 1, see §6 — the blast radius is one directory.

### 3.2 The rule that protects the cost controls

**No module other than `services/api/gateway/` may call an LLM provider.** mureo is used for *data
and dispatch only*; its own AI-facing surfaces (the MCP server, the skill commands, the strategy
grounding) are not wired in. If a mureo call path turns out to make a model call, wrap it or drop
it. This invariant is what the ledger, the daily ceiling and the kill switch depend on.

---

## 4. Port manifest — what comes across from HELM

Carry over, unchanged where possible. This is the work that cannot be bought or re-derived cheaply.

| From HELM | To HELM02 | Notes |
|---|---|---|
| `workers/helm_worker/agents/governor/graph.py` | `modules/governor/` | Star topology + `HandoffEnvelope`. **Drop** the `except: pass` canned fallbacks in all four nodes — replace with a `degraded` verdict on the envelope |
| `workers/helm_worker/checkpoint.py` | `modules/governor/` | SQLite checkpointer + `interrupt()`. Durable resume is the HITL gate's whole value |
| `workers/helm_worker/agents/media_buyer/` `apply_policy()` | `modules/budget/` | ±25% shift cap + budget conservation. **Do not** bring `data.py` / `SAMPLE_CAMPAIGNS` |
| SEBI `compliance.check()` | `modules/compliance/` | The regulatory moat. Nothing in either external repo does SEBI |
| `api/app/gateway/` (whole package) | `services/api/gateway/` | policy → budget reserve → adapter → reconcile → usage; integer micro-dollar rate card; kill switch; policy-authority clamps |
| `api/app/knowledge/citations.py` | `services/api/` | Citation verifier — keep for *qualitative* grounding only (brand voice, SEBI rules, personas) |
| `api/app/auth/`, `api/alembic/` | `services/api/` | Identity spine. Keep `tenant_id` columns; stop building tenant *features* until tenant #2 |
| `api/tests/` (237 green) | `services/api/tests/` | Port with the code. Do not restart test coverage from zero |

**Explicitly left behind:** all of `web/` (9,200 lines, 14 pages, 11 fixture-driven);
`web/lib/server/agent-runner.ts` `simulateGovernorRun` / `simulateSpecialistRun` (~370 lines of
fabricated relay); `web/lib/server/ad-platforms/` (~400 lines, superseded by mureo, and it invents
`budget-${campaignId}` / `ag-${campaignId}` resource ids that are not real Google resource names);
`web/data/*.json` stores; `workers/.../data_sources.py` (a symptom of the missing Phase 2, now
superseded by mureo); `helm-mockup-v4.html`; `scratch/`.

---

## 5. Phases

Each phase ends with a check that can actually be run. No phase starts before the previous check
passes.

### Phase 0 — Repo and custody (≈1 day)
1. Scaffold the §3 tree. Pin `mureo==0.10.47` exactly.
2. Resolve the Python version question in §2.1.
3. Implement `HelmSecretStore` against the `mureo.core.secret_store.SecretStore` Protocol, backed
   by server-side storage. Assert in a test that no code path reads `~/.mureo/`.

**Check:** `pytest` proves mureo resolves credentials through `HelmSecretStore` and the home
directory is never touched.

### Phase 1 — Core port (≈4 days)
4. Port the gateway package and its tests. Set a real `ANTHROPIC_API_KEY`.
5. Port the star graph, envelopes, checkpointer and HITL. Remove every canned fallback; a failing
   node emits `degraded` and the run says so.

**Check:** stop the API server, dispatch a mission → the console reports a gateway failure. It must
be **impossible** to get a green seven-hop relay while the API is down. `/health` reads
`gateway: "live"`.

### Phase 2 — Ads read via mureo (≈3 days)
6. `modules/ads/` implements `Connector.fetch_campaigns()` over `mureo.google_ads` and
   `mureo.meta_ads`, returning `CampaignSnapshot`.
7. Wire `mureo.byod` as the no-OAuth path — Excel bundle import gets real Finnovate numbers in
   before OAuth is finished.
8. **The Analyst reads the snapshot.** Schema its findings (`trends[]`, `top_angles[]`,
   `decay_signals[]`, `per_campaign[]`). No regex scraping of prose. Numbers come from the ad
   accounts; rules and voice come from the doc corpus via the citation verifier.

**Check:** two consecutive runs on different snapshots produce Analyst findings whose numbers match
*their own run's* snapshot and differ from each other. Campaign ids in the proposal are real
platform ids.

### Phase 3 — Creative and compliance (≈3 days)
9. `modules/creative/` emits `brief → script → creative → caption` as a typed schema, through the
   gateway.
10. SEBI verifier gates it, with the existing loopback (up to 2 retries) preserved.

**Check:** a non-compliant headline is caught deterministically, cited to a SEBI clause, and the
loopback produces a passing variant.

### Phase 4 — The Governor executes (≈4 days)
11. `modules/execution/` calls `Connector.apply_budget()` / `deploy_creative()` over mureo's write
    paths — with **real** resource lookups, not string-templated ids.
12. `execute()` dispatches inside the audited graph and emits one execution envelope per platform
    response. `HELM_ADS_DRY_RUN=true` by default; dry-run returns the exact payload it would send.
13. Adopt `mureo.rollback`'s allow-list model for reversals.

**Check:** approve a mission in dry-run → the log shows exact API payloads. Flip the flag on a test
campaign with a ₹100 budget → the change appears in Ads Manager *and* in the audit trail.

### Phase 5 — UI and one store (≈3 days)
14. Four screens: Run, Proposal, Approvals, Audit. One run store — the API. No JSON files.
15. One mode badge showing three independent facts: **data** live/byod/synthetic · **model**
    live/replay · **ads writes** dry-run/live.

**Check:** restart both services mid-run; the approvals inbox and the run history agree.

**Total ≈ 18 working days.** Comparable to the 2–3 weeks Phases A–E would have cost inside HELM,
but the connector layer arrives tested rather than written.

---

## 6. Risks accepted knowingly

| Risk | Mitigation |
|---|---|
| **mureo bus factor is 1** — 195 of the last 200 commits are one author (Logly, Inc.) | Apache-2.0; we can fork. The `Connector` protocol in §3.1 keeps the blast radius to one directory |
| **Underscore-prefixed internals** — `_ads.py`, `_creative.py`, `_gaql_validator.py` are private; the supported surface is the CLI and MCP server | Pin the exact version. Treat a mureo upgrade as a code change with its own test run, never a routine bump |
| **mureo's local-first design assumptions** may surface elsewhere than the secret store | Phase 0's assertion test. Add more as they're found |
| **Python 3.13/3.14 unverified** (§2.1) | Resolve in Phase 0, before anything is built on it |
| **Losing HELM's 237 green tests** if the port is sloppy | Port tests *with* the code, same commit. Do not defer |
| **A second creative/compliance authority** creeping in from simplicio | No code from that repo. Schema shape only |

---

## 7. Invariants — the things that make this HELM and not a chatbot

1. The **model gateway is sole egress**. Workers hold no provider keys.
2. The **Governor is the hub**. No agent-to-agent edges; every hop is a typed envelope.
3. **Deterministic checks stay in code** — SEBI rules and the ±25% cap are not prompt-dependent.
4. **A degraded run is labelled degraded**, in the envelope and in the UI. Nothing is ever
   fabricated to keep a screen green.
5. **One run store, one executor, one campaign table.** Any second copy is a bug.
