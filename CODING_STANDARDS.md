# Coding standards

One rule per line. `[check: <name>]` means CI enforces it in the job of that name; `[judgement]` means a reviewer judges it.

## Everything
- Hyphen ( - ), never the em-dash, in anything shipped; `challenge/` is third-party text kept byte for byte and is exempt. [check: em-dash]
- No fabricated metrics: honest capability statements or real, sourced numbers only. [judgement]
- Comments, in any language, only state a constraint that cannot be read from the code. [judgement]
- No secrets in tracked files; keys come from local env files that `.gitignore` covers. [check: secrets]
- Errors fail loudly: a caught error is handled with intent or re-raised with context; no `except Exception: pass`, no swallowed promise rejection, no `|| true` without a comment naming why. [judgement]
- Validate input at trust boundaries: the request JSON, anything from the network, a file a person wrote. [judgement]
- Package installs and downloaded binaries are pinned to an exact version, and a downloaded binary is checksum-verified before it runs; GitHub Actions may use a major tag; no `latest`, no unpinned `pip install`, no piping a download into a shell. [judgement]
- Audit what a new dependency pulls in before adding it; install into an isolated environment (venv, `uvx`, `npm ci`), never system-wide. [judgement]
- Dead code is deleted outright; git keeps the history, so no commented-out blocks. [judgement]
- Prefer deep modules: a lot of behaviour behind a small interface. A shallow wrapper whose interface is as big as its body is a finding. [judgement]

## Privacy (this product)
- Opted-out patients are filtered at the data-access layer, once, before any query runs; no query path can reach them. [judgement]
- The small-cell rule is applied in one shared function that every statistical output passes through; no output formats a number itself. [judgement]
- Patient-level rows never appear in logs, error messages, test output, or API responses outside the SPE. [judgement]
- SPE download endpoints return non-personal data only; the block is enforced server-side, never only in the UI. [judgement]

## Shell
- Every shell script parses. [check: shell]
- Shell scripts are shellcheck-clean at warning level. [check: shell]
- No recursive deletes of any form; remove paths one at a time. [judgement]
- No hard resets of git history; move a branch with `git branch -f` or a fast-forward merge, or let the PR merge reconcile. [judgement]

## Python
- Python files compile. [check: python]
- Python is ruff-clean. [check: python]

## TypeScript / JavaScript
- TypeScript runs with `strict` on. [judgement]

## Tests
- Tests exercise behaviour through the interface (stdin, args, env, exit code, output, return value), never by reading the source text. [judgement]
- Every tracked test file either runs in CI or carries a one-line exclusion reason in the workflow. [judgement]
- The 10 challenge requests are the regression suite: a change to decisions or numbers is a test change first. [judgement]

## Docs
- Internal markdown links resolve. [check: python]
- Tracked JSON parses. [check: python]
- Agent and worker prompts use absolute paths only. [judgement]
- `docs/decisions/log.md` is append-only. [judgement]
