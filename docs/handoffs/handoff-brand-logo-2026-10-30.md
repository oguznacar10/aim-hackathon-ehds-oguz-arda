# Handoff: .Gatekeeper wordmark - 2026-10-30

## What changed
- The product name is now Gatekeeper, shown as the wordmark ".Gatekeeper" in the header: a blue dot (`--statistical`, the same colour as the APPROVE_STATISTICAL status dot) before the bold name. "Health Data Access Body" stays as the subtitle.
- Browser tab title "Gatekeeper - Health Data Access Body" and a blue dot favicon (inline SVG data URI, no new route).
- `web.py` server banner and README intro say Gatekeeper instead of Datenzugang.

## Verified
- `pytest -q`: 186 passed. `ruff check .`: clean.
- Playwright: header renders ".Gatekeeper" with the dot in rgb(29, 78, 137); tab title as above.

## Open
- None known. The README heading still names the team repo, on purpose.

## Next step
- Merge after Oguz or Arda says so.
