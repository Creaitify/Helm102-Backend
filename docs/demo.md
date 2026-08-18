# HELM Orchestration Demo Plan

## Goal

Build a single marketing operations product that can:

1. read campaign data from Meta and Google Ads,
2. analyze performance,
3. generate new ad copy and video requirements,
4. propose budget changes,
5. run compliance checks,
6. route everything through a Governor for approval,
7. push approved changes back to the ad platforms.

This demo is designed to show the working product path end-to-end, while keeping the initial build small enough to start immediately.

## Why this approach

We are not building a simple chatbot. We are building an orchestration system with specialized workers.

The system will reuse two existing foundations:

- **Mureo** for ad operations, platform actions, and campaign workflows.
- **Loop Marketing** for creative generation, scripts, copy, and video requirements.

A central **Governor** decides what to call, in what order, and whether the result is ready for approval.

## What the demo should prove

The demo should answer these questions clearly:

- Can the system ingest campaign data from Meta and Google?
- Can it analyze performance and identify what needs to change?
- Can it generate ad copy and video requirements from the analysis?
- Can it propose a budget shift?
- Can it check compliance before anything is approved?
- Can the Governor coordinate the flow and keep the process controlled?
- Can an operator approve the result and see what would be executed?

## Demo scope for phase 1

This first version should be narrow and visible.

### In scope

- One dashboard or control page
- One campaign run at a time
- One Governor
- One ads worker path based on Mureo
- One creative worker path based on Loop Marketing
- One compliance step
- One budget proposal step
- One approval step
- One audit trail of the run

### Out of scope for now

- Multi-tenant billing
- Advanced rollback
- Complex campaign scheduling
- Full production deployment hardening
- Deep analytics warehouse integration

## Working flow

The demo flow should look like this:

1. **User enters a goal**
   - Example: reduce cost per lead or improve conversions.

2. **Governor classifies the task**
   - decides whether it needs campaign analysis, creative refresh, budget review, compliance review, or all of them.

3. **Governor calls Mureo-based ad operations**
   - fetch campaign data
   - summarize performance
   - identify underperforming campaigns

4. **Governor calls Loop Marketing for creative work**
   - generate ad copy
   - generate hooks and captions
   - generate video requirements

5. **Governor calls compliance review**
   - checks the generated content against policy rules
   - flags risky claims or unsafe wording

6. **Governor prepares a proposal**
   - shows the recommended changes
   - shows the budget move
   - shows compliance status
   - shows the final approval summary

7. **Human approves or rejects**
   - approved changes move to execution
   - rejected changes return to revision

8. **Execution is logged**
   - the system stores what was proposed, what was approved, and what would be pushed to Meta/Google

## Architecture for the demo

### Core

- **Governor**
  - task router
  - state holder
  - policy enforcer
  - final decision coordinator

### Worker layer

- **Mureo worker**
  - campaign ingestion
  - analytics summary
  - budget and platform actions

- **Loop Marketing worker**
  - creative briefs
  - copy generation
  - video requirements

- **Compliance worker**
  - deterministic rules
  - approval gating

### UI

- one web screen for:
  - creating a run
  - watching the worker chain
  - viewing the proposal
  - approving or rejecting
  - seeing the audit trail

## What the boss should see

The boss-friendly version of the product is simple:

- a clean dashboard,
- a visible step-by-step run,
- a proposal with generated creative and budget changes,
- a compliance verdict,
- and a clear approve/reject button.

The point is not to impress with complexity. The point is to show that the system is controllable, auditable, and useful.

## Build phases

### Phase 1: Demo shell
- create the app skeleton
- create the Governor interface
- create a run page
- create a proposal page
- create a basic audit log view

### Phase 2: Mureo integration
- connect the ad-ops worker path
- ingest campaign data
- produce performance summaries
- surface campaign actions inside the demo

### Phase 3: Loop Marketing integration
- connect the creative worker path
- generate copy and video requirements
- return structured creative outputs to the Governor

### Phase 4: Compliance and approval
- add deterministic compliance rules
- block unsafe output
- add human approval flow
- store the final decision

### Phase 5: Execution readiness
- prepare the write-back path for Meta/Google
- keep execution behind approval
- log every action for review

## Success criteria for the demo

The demo is successful if it can do all of the following:

- accept a goal,
- route work through the Governor,
- call the right worker at the right time,
- show useful results from campaign data,
- generate creative suggestions,
- show a compliance verdict,
- and produce a clean approval screen.

## What this means for the product

If this demo works, it proves the product can become a real marketing operating system instead of a collection of disconnected tools.

It also proves the architecture choice:

- Mureo is the operations brain for ad platforms.
- Loop Marketing is the creative generation brain.
- The Governor is the control layer.
- The human is the final decision-maker.

## Approval ask

Approve this plan so the build can start with the demo shell and Governor first, then connect Mureo and Loop Marketing as worker modules.

---

## One-line version

**Build a governor-led marketing orchestration demo that ingests ad data, generates creative, checks compliance, proposes budget changes, and presents a clean approval flow.**
