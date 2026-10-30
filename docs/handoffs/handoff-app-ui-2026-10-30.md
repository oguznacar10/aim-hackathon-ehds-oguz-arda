# Handoff: web app (applicant and staff screens), 2026-10-30

## What changed
- `src/gatekeeper/web.py`: stdlib HTTP server (no new dependency) over `pipeline.handle()`. Endpoints: `GET /api/examples`, `POST /api/decide`, `POST /api/spe/<id>/download` (always 403, logged), `GET /api/cases`, `GET /api/cases/<id>`, `POST /api/cases/<id>/confirm|overrule`. Cases live in memory only.
- `src/gatekeeper/static/`: plain HTML, CSS and JS, no build step. Applicant: request form with the 10 examples, decision notice with the four-step ruling path, reasons with article notes in the margin, statistics table with the small-cell footnote, secure-room panel with a real blocked download. Staff: case list with "needs review" first, case file with both readers, evidence highlight, query plan and SQL, SPE audit log, confirm or overrule.
- `pipeline.handle()` now also returns `reading` (the reader's judgments and the keyword second opinion), request text only.
- Fonts load from Google Fonts; offline the fallback stacks apply.

## Verified
- `pytest -q`: 106 passed, including `tests/test_web.py` over real HTTP. `ruff check .`: clean.
- With the OpenRouter key: R02 REJECT, R05 APPROVE_SPE, R09 APPROVE_STATISTICAL through `/api/decide`; download returns 403.

## Open
- Not yet clicked through by a human on every request; README and video still to do.
