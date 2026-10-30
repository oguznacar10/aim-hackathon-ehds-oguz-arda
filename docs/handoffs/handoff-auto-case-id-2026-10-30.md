# Handoff: applicant form simplified - 2026-10-30

## What changed
- No "Case number" box. `web.decide` gives a request without an `id` the next free `C-NNN`; samples keep R01 to R10.
- No Applicant name, Organisation or Country fields. The form shows "Signed in as Dr. Lena Berger, Vienna Institute for Population Health (demo account)" (fictional, `DEMO_APPLICANT` in `app.js`). Loading a sample switches the line and the submitted applicant to the sample's.
- Small light "i" tooltips on each label (CSS only, `aria-describedby`).

## Verified
- `pytest -q`: 140 passed. `ruff check .`: clean.
- Playwright: R01 shows its own applicant; clearing goes back to the demo account; a new request comes back as `C-NNN` for the demo institute.

## Open
- Case numbers are in memory and restart at C-001 with the server.
- No real login; the demo account is fixed.

## Next step
- Merge after Oguz or Arda says so.
