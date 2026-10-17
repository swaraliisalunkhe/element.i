# Code Apex

**Team:** No Limits
**Problem statement:** IM-02 - Autonomous AI QA Engineer

Code Apex automatically explores a web application, generates tests, runs them
in a browser, and reports bugs with screenshot evidence.

## Status

Early setup. This README is a stub and will be completed by Member D.

## Repository layout

| Folder | Purpose | Owner |
|---|---|---|
| `backend/` | FastAPI server, database, orchestrator, agents | A (core/api/db/schemas), C (agents/services) |
| `sample_app/` | Web app with deliberately planted bugs | B |
| `frontend/` | Next.js dashboard | D |
| `shared/contracts/` | JSON examples of the shared data formats | A |
| `benchmark/`, `docs/` | Benchmarks and documentation | D |
| `data/` | Generated databases and screenshots (not tracked by Git) | - |

## Getting started

Setup instructions will be added by Member D after the first integration.

## Team workflow

1. Never commit directly to `main` (the first skeleton commit was the only exception).
2. Create a branch named `feat/<member>-<topic>`, for example `feat/a-contracts`.
3. Open a pull request and get one approval from a different member.
4. Never commit `.env` or any API key.