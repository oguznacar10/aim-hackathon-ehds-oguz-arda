# AIM Hackathon EHDS - Oguz & Arda

A Health Data Access Body for the European Health Data Space (Regulation (EU) 2025/327, Chapter IV). Built at the AIM Healthcare Hackathon Vienna, 29-30 October 2026, Track 3.

It takes a health data request as JSON and, automatically:
1. decides `REJECT`, `APPROVE_STATISTICAL` or `APPROVE_SPE` and cites the articles,
2. computes anonymised statistics under the small-cell rule,
3. or copies the selected patients' records into a secure processing environment with downloads blocked,
4. and shows decision and reason to the applicant and to staff.

## Status

Skeleton. Stack decision pending (see `docs/decisions/log.md`). Nothing runs yet.

## Run it

To be written once the stack is decided.

## Architecture

To be written: which components we built, how they work together, which models or services we use. (The submission requires this section.)

## Metric results on the 10 requests

| Metric | Target | Ours |
|---|---|---|
| Correct decisions | 10 of 10 | not run |
| Correct numbers | 6 of 6 | not run |
| Privacy leaks | 0 | not run |
| Consistency over 3 runs | 10 of 10 | not run |
| Slowest request | under 60 s | not run |

## Repository

Start at `docs/MAP.md`. Rules for agents in `AGENTS.md`, for humans in `CONTRIBUTING.md`.

Synthetic data only. The challenge data under `challenge/` is the organisers' synthetic set, vendored byte for byte.
