#!/usr/bin/env bash
# Fails when a diff ADDS a line containing an em dash (U+2014). Renames are kept (R) so only edited lines of a renamed file are scanned.
# Usage: em-dash-guard.sh [base-ref]   (default origin/main; compares base...HEAD)
# Exempt: challenge/ (organisers' text kept byte for byte) and .gitleaksignore.
set -u

base="${1:-origin/main}"
em=$'\xe2\x80\x94'

# Only a root commit may pass without a base; any other unknown ref still fails closed below.
if ! git rev-parse -q --verify "$base^{commit}" >/dev/null && ! git rev-parse -q --verify 'HEAD^' >/dev/null; then
  echo "em-dash-guard: base '$base' does not exist and HEAD is a root commit; nothing to compare"
  exit 0
fi

diff=$(git -c core.quotepath=off diff "$base"...HEAD -U0 --diff-filter=AMR -- . \
  ':(exclude)challenge/**' ':(exclude).gitleaksignore') || { echo "em-dash-guard: git diff against '$base' failed" >&2; exit 2; }

hits=$(printf '%s\n' "$diff" | awk -v d="$em" '
  /^diff --git / { inhunk = 0; next }
  !inhunk && /^\+\+\+ / { f = substr($0, 5); sub(/^b\//, "", f); next }
  /^@@ / { inhunk = 1; match($0, /\+[0-9]+/); n = substr($0, RSTART + 1, RLENGTH - 1) + 0; next }
  inhunk && /^\+/ { if (index($0, d)) print f "\t" n "\t" substr($0, 2); n++ }
')

if [ -z "$hits" ]; then
  echo "em-dash-guard: clean"
  exit 0
fi

while IFS=$'\t' read -r f n text; do
  echo "em-dash-guard: $f:$n: ${text:0:120}"
done <<< "$hits"
echo "em-dash-guard: added lines contain an em dash (U+2014); use a hyphen ( - )" >&2
exit 1
