# Handoff: animated welcome in the empty notice area - 2026-10-30

## What changed
- Before the first decision, the right-hand notice area shows `#welcome`: an inline SVG of the three hospital databases linked through .Gatekeeper to researchers (Vienna, Berlin, Lisbon), with dashed lines flowing and small dots travelling along them, plus three short lines of text.
- It is replaced by the pending notice on submit, and restored if the request fails.
- `prefers-reduced-motion`: the CSS animations stop and the travelling dots (SMIL `animateMotion`) are hidden.

## Verified
- `pytest -q`: 186 passed. `ruff check .`: clean.
- Playwright at 1280 px and 390 px: welcome renders, no page errors, and it is gone after R01 is decided.

## Open
- The city names are illustrative, not data. Text inside the drawing is small on phone widths.

## Next step
- Merge after Oguz or Arda says so.
