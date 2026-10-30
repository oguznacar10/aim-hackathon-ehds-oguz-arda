# Handoff: animated welcome in the empty notice area - 2026-10-30

## What changed
- Before the first decision, the right-hand notice area shows `#welcome`: an inline SVG of the three hospital databases linked through .Gatekeeper to researchers (Vienna, Berlin, Lisbon), with dashed lines flowing and small dots travelling along them, plus three short lines of text.
- It is replaced by the pending notice on submit, and restored if the request fails.
- `api()` in app.js now turns a fetch rejection (server unreachable) into an error result, so Submit no longer stays stuck on "Deciding...".
- Staff view: the empty case-file area shows its own drawing (`#staff-welcome`): a case file at the top sends a query dot down to each of the three hospital databases, each database top glows softly when the query dot arrives, and a hollow dot (the total) travels back up. No researchers on purpose: staff look at the databases. Opening a case replaces it.
- `prefers-reduced-motion`: the CSS animations stop and the travelling dots (SMIL `animateMotion`) are hidden.

## Verified
- `pytest -q`: 191 passed (re-run 2026-10-30 on this branch after the id fix). `ruff check .`: clean.
- Playwright at 1280 px and 390 px: welcome renders, no page errors, and it is gone after R01 is decided.
- Browser test by the testing agent: R01/R05/R02 decisions, Staff navigation, validation and HTTP errors, server outage recovery and retry, reduced motion (dots hidden, frames identical), 390 px without overflow.

## Open
- The city names are illustrative, not data. Labels inside the drawing get very small (about 6 px) on phone widths; the sentences stay readable.

## Next step
- Merge after Oguz or Arda says so.
