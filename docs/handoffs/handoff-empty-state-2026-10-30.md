# Handoff: animated welcome in the empty notice area - 2026-10-30

## What changed
- Before the first decision, the right-hand notice area shows `#welcome`: an inline SVG of the three hospital databases linked through .Gatekeeper to researchers (Vienna, Berlin, Lisbon), with dashed lines flowing and small dots travelling along them, plus three short lines of text.
- It is replaced by the pending notice on submit, and restored if the request fails.
- `api()` in app.js now turns a fetch rejection (server unreachable) into an error result, so Submit no longer stays stuck on "Deciding...".
- Staff view: the empty case-file area shows the same drawing (`#staff-welcome`, SVG cloned from `#welcome` in app.js with `staff-` id prefixes so the `mpath` links stay unique) and three lines for staff. Opening a case replaces it. Same symbols, different motion (`.net-staff`): dots run researchers to hospitals, the databases light up in turn, and a dashed ring turns around the hub instead of the pulse.
- `prefers-reduced-motion`: the CSS animations stop and the travelling dots (SMIL `animateMotion`) are hidden.

## Verified
- `pytest -q`: 187 passed. `ruff check .`: clean.
- Playwright at 1280 px and 390 px: welcome renders, no page errors, and it is gone after R01 is decided.
- Browser test by the testing agent: R01/R05/R02 decisions, Staff navigation, validation and HTTP errors, server outage recovery and retry, reduced motion (dots hidden, frames identical), 390 px without overflow.

## Open
- The city names are illustrative, not data. Labels inside the drawing get very small (about 6 px) on phone widths; the sentences stay readable.

## Next step
- Merge after Oguz or Arda says so.
