# Original User Request

## 2026-08-18T06:59:59Z

Build and execute a complete, production-grade governed marketing orchestration system with Governor star relay coordination, Gemini 2.5 worker models, persistent React workspaces, and SQLite coherent synthetic datasets.

Working directory: c:\Users\hp\HELM02
Integrity mode: development

## Requirements

### R1. Governor-Led Star Relay Orchestration Engine
- Ingest marketing objectives and classify tasks through a central Governor coordinator.
- Dispatch typed envelopes across workers: Ad-Ops Analyst, Creative Studio, SEBI Compliance Engine, and Budget Optimizer.
- Save durable state checkpoints after every hop so intermediate progress and reports are never lost.

### R2. Proper Gemini 2.5 Model Invocation & Gateway
- Route all LLM requests through the Model Gateway using official Google Gemini models (`gemini-2.5-pro`, `gemini-2.5-flash`).
- Enforce structured JSON schemas for creative generation, video scripting, and compliance audits.

### R3. Dedicated Persistent Multi-Agent React Workspaces (White & Blue Theme)
- Modern React SPA built with Vite and Lucide React adhering to Google Stitch design system specifications.
- 7 dedicated workspaces: Governor HQ, Ad-Ops Workspace, Creative Studio, Compliance Shield, Budget Optimizer, Execution Engine, and Audit Trail.
- Non-vanishing state store: switching between tabs or reloading preserves all active runs, metrics, generated assets, and audit logs.
- High-aesthetic White & Royal Blue palette (`#F8FAFC` slate background, `#FFFFFF` pure white cards with `#E2E8F0` borders, `#2563EB` royal blue branding).

### R4. SQLite Coherent Synthetic Dataset Engine
- Generate multi-channel synthetic marketing campaigns with 30-60 day coherent variances (CTR decay, ROAS shifts, ad fatigue, non-compliant copy flags).
- Provide one-click scenario presets for quick testing and automated regression suites.

### R5. SEBI Compliance & Human Approval Gate
- Deterministic statutory rule checks preventing guaranteed return claims and enforcing mandatory disclaimers.
- Strict human-in-the-loop signoff gate preventing unauthorized ad platform dispatches.

## Acceptance Criteria

### Backend & Orchestration
- [x] All 75 automated tests passing with zero failures.
- [x] Checkpointer persists every hop envelope and resumes upon human decision.

### Frontend & UI
- [x] React SPA compiles and bundles cleanly (`npm run build` exits 0).
- [x] Switching between workspace tabs preserves live state and agent reports.
- [x] White & Royal Blue theme matches Stitch design guidelines.

### Synthetic Data & Compliance
- [x] SQLite synthetic generator creates multi-channel campaigns with coherent decay signals.
- [x] SEBI compliance verifier detects prohibited claims and provides instant feedback.

## 2026-08-19T04:07:13Z

Universal Messy Marketing Dataset Ingestion & Automated Data Cleaning Pipeline for HELM. Ingest, sanitize, profile, and transform multi-platform marketing datasets (Google Ads, Meta Ads, TikTok Ads, LinkedIn Ads) with missing columns, varied column aliasing (`ad_spend`, `revenue`, `CPC`), decimal/fractional CTR formats, and automatic campaign name synthesis for full Governor and Analyst downstream orchestration.

Working directory: c:/Users/hp/HELM02
Integrity mode: development

## Requirements

### R1. Universal Column Aliasing & Metric Auto-Derivation
- Expand canonical column aliasing in `modules/ads/byod_importer.py` to support `ad_spend`, `adspend`, `revenue`, `conv_value`, `sales`, `cpc`, `cost_per_click`, `campaign_type`, `industry`, `country`, `date`, `day`.
- Auto-derive missing metrics where possible:
  - If `roas` is missing but `revenue` and `spend` exist: compute `roas = revenue / spend`.
  - If `spend` is missing but `clicks` and `cpc` exist: compute `spend = clicks * cpc`.
  - If `cpa` is missing but `spend` and `conversions` exist: compute `cpa = spend / conversions`.
  - If `ctr` is given as a decimal fraction (`0.0 < ctr <= 1.0`): normalize to percentage format (e.g., `0.0353` → `3.53%`).

### R2. Multi-Platform Support & Intelligent Campaign Synthesis
- Update `Platform` enum in `modules/ads/contracts.py` and `modules/creative/schema.py` to support `GOOGLE_ADS`, `META_ADS`, `TIKTOK_ADS`, `LINKEDIN_ADS`, `BYOD`.
- If `campaign_name` is absent in the source dataset, synthesize a descriptive campaign name from available contextual dimensions: `[{platform}] {campaign_type} - {industry} ({country})` with deterministic slug identifiers.

### R3. Automated Data Cleaning, Profiling & Ingestion
- Clean and sanitize input data: strip whitespace, handle null/missing values, remove unquoted carriage returns, and filter empty rows.
- Store the user's multi-channel 300+ row dataset in `services/api/data/sample_multichannel_campaigns.csv` and activate it in the BYOD dataset store.
- Enable full Governor and Analyst workflows to run directly on the cleaned multi-channel dataset.

### R4. Automated Verification & Regression Prevention
- Add comprehensive pytest unit tests verifying the exact user-supplied dataset (Google Ads, TikTok Ads, Meta Ads with 300+ rows).
- Ensure all 215+ backend tests and 21+ frontend vitest tests pass with 0 errors.

## Acceptance Criteria

### Data Ingestion & Cleaning
- [x] User-supplied 300+ row CSV parses with 100% success into `CampaignSnapshot`.
- [x] Columns `ad_spend`, `revenue`, `CTR` (decimal), `CPC`, `conversions`, `CPA`, `ROAS` are correctly mapped and normalized.
- [x] Missing campaign names are synthesized as descriptive multi-dimensional strings.
- [x] Google Ads, Meta Ads, and TikTok Ads are mapped to their respective `Platform` enums.
- [x] Cleaned dataset is accessible via `/api/byod/upload`, `/api/byod/current`, and used by `/api/runs`.

### Test & Build Health
- [x] Pytest suite passes all tests including dedicated messy dataset tests.
- [x] Vitest suite passes all 21 frontend tests.
- [x] Frontend builds cleanly with Vite (`npm run build`).

## 2026-08-19T12:36:24Z

This is a single self-contained fix; keep it small and focused.

Implement an agent-side file attachment interface in both the Agent Console and Pipeline launcher, enabling operators to upload/attach datasets (.csv, .xlsx, .json) directly when interacting with agents. Automatically activate the uploaded data as the primary BYOD dataset (bypassing synthetic data), and configure resilient background execution with streaming/polling so agent runs can proceed indefinitely without timing out.

Working directory: c:\Users\Admin\OneDrive\Desktop\HELM-102-BACKEND-V2\Helm102-Backend
Integrity mode: development

## Requirements

### R1. Agent Console & Pipeline File Attachment Interface
- Add an intuitive inline file attachment button (with drag-and-drop support) to the input bar in both the Agent Console (AgentsScreen.jsx) and the Pipeline run launcher (PipelineScreen.jsx).
- Support .csv, .xlsx, .xls, and .json files, displaying an attachment chip with filename and remove action before submission.

### R2. Seamless BYOD Auto-Activation
- When a prompt is submitted with an attached file, the backend immediately parses and activates the dataset as the active byod data source.
- All subsequent agent reasoning (Analyst diagnostics, Governor plan formulation, Creative copy generation, Media Buyer budget allocation) executes against the imported dataset, bypassing synthetic data.

### R3. Timeout-Free Resilient Execution
- Ensure long-running agent tasks and Governor pipeline runs execute asynchronously with live polling / resilient streaming.
- Remove hard HTTP client timeouts on agent invocation paths so execution continues cleanly until the model returns its full response.

## Acceptance Criteria

### UI / UX
- [ ] The Agent Console and Pipeline launcher have an attachment button (paperclip/upload icon) and support drag-and-drop file attachment.
- [ ] Selected file displays a clear pill/chip showing the filename and a remove button before sending.

### Data Ingestion & Context Switching
- [ ] Submitting a prompt with a file automatically parses the file and switches the backend data source to byod.
- [ ] Agent responses directly reflect the metrics, campaigns, and platforms contained in the uploaded file.

### Execution & Timeout
- [ ] Agent and Governor tasks run to completion regardless of duration without throwing timeout exceptions.
- [ ] Live progress state and final responses render seamlessly in the UI.
