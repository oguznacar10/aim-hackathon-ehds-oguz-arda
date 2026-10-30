# Handoff: applicant form simplified - 2026-10-30

## What changed
- No "Case number" box. `web.decide` gives a request without an `id` the next free `C-NNN`; samples keep R01 to R10.
- Applicant name, Organisation and Country stay as editable fields: name on its own row, organisation next to a narrow country box. A "Signed in as" line was tried and dropped again at Oguz's request.
- Small light "i" tooltips on each label (CSS only, `aria-describedby`).

## Verified
- `pytest -q`: 141 passed. `ruff check .`: clean.
- Playwright: a new request comes back as `C-NNN`; loading R01 fills name, organisation and country.

## Open
- Case numbers are in memory and restart at C-001 with the server. Fixed on `claude/case-id-restart`: an id whose `spe/<id>` folder exists is skipped, so an old audit log is not reused. Case records themselves are still lost on restart.

## Next step
- Merge after Oguz or Arda says so.
