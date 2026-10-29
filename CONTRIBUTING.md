# Contributing

Two people, one weekend. The rules exist so neither of us has to re-read the other's work to trust it.

## Branches and PRs
- `main` is protected: pull request required, `ci-green` check required, no force pushes, linear history (squash merge).
- Branch names: `<who>/<topic>`, for example `oguz/query-generator`.
- One topic per PR. Open it early as a draft so the other one sees direction, not just results.
- The PR template asks three things: what changed, how you verified it (command + output), what is still open. Fill all three.
- Either of us may merge a green PR of the other. Merge your own only after the other has seen it or after a note in Discord.

## CI
- `secrets` (gitleaks, full history), `em-dash` (added lines), `shell` (syntax + shellcheck + guard test), `python` (ruff + pytest), `node` (only once `package.json` exists), and `ci-green` which gates on all of them.
- Red CI is fixed in the same PR. If a check is wrong, the fix to the check is its own PR with the reason in the description.
- A gitleaks hit on any branch reddens every PR until it is fingerprinted in `.gitleaksignore` with a reason comment, or the secret is rotated and the history rewritten by agreement of both.

## Decisions and handoffs
- `docs/decisions/log.md`: append-only, dated entries, PROPOSED or DECIDED, with the why.
- `docs/handoffs/`: one file per session end. The next session starts from the newest one.
- `docs/plans/`: implementation plans, one file per plan, dated.

## Agents
- Every agent reads `AGENTS.md` first. Claude Code reads `CLAUDE.md`, which imports it.
- Agents open PRs; humans merge. An agent never pushes to `main`.
