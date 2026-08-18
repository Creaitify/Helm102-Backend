# AGENTS.md — HELM Orchestration Build Guide

## Purpose
This document is the build guide for the coding agent.
It defines how the system should work, how the pieces fit together, and how progress must be tracked.

This project is a **governed marketing orchestration system**.
It is not a loose set of agents.
It is a controlled workflow with a Governor, specialized workers, compliance checks, and human approval.

## Product goal
The application should:

1. ingest campaign data from Meta and Google,
2. analyze performance,
3. generate ad copy and video requirements,
4. propose budget changes,
5. verify compliance,
6. present a human approval step,
7. execute only after approval,
8. keep a complete audit trail.

## External foundations
The build may reuse behavior and ideas from:

- **Mureo** for ad operations, platform actions, and campaign workflows.
- **Loop Marketing** for creative generation, scripts, captions, and video requirements.

Do not directly mash repositories together.
Instead, wrap reusable behavior behind clean interfaces.

## System model
The system should use a **Governor-led orchestration flow**.

- The **Governor** decides what happens next.
- Workers handle narrow jobs.
- Workers return structured results.
- The Governor merges those results, applies policy, and decides whether to continue.
- A human makes the final approve/reject decision.

## Expected flow
A run should usually look like this:

1. user goal enters the system,
2. Governor classifies the task,
3. ad-ops worker fetches and summarizes data,
4. creative worker generates copy and video requirements,
5. compliance worker checks risky language,
6. budget worker proposes allocation changes,
7. Governor assembles a final proposal,
8. human approves or rejects,
9. execution happens only after approval.

## Build rules
Follow these rules while developing:

- keep modules small and focused,
- keep the Governor in control,
- never let UI code hold provider secrets,
- keep OAuth and credentials in backend-controlled storage,
- use deterministic checks where possible,
- make fallbacks visible,
- log every meaningful step,
- prefer typed interfaces and structured outputs,
- avoid hidden prompt-only logic.

## What to build first
Work in this order:

1. project scaffold,
2. data contracts,
3. Governor and run state,
4. worker interfaces,
5. ad-ops integration,
6. creative integration,
7. compliance checks,
8. approval flow,
9. audit trail,
10. execution path.

Do not jump straight to live execution before approval and logging work.

## Suggested structure
A clean build can be organized like this:

```text
apps/
  web/
services/
  api/
modules/
  governor/
  ads/
  creative/
  compliance/
  budget/
  execution/
  audit/
docs/
  demo.md
  AGENTS.md
  TASK_LOG.md