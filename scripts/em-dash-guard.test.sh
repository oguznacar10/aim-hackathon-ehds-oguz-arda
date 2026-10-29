#!/usr/bin/env bash
# Self-check for em-dash-guard.sh against throwaway git repos. The temp dir is left for the
# OS to reap: a git repo cannot be removed here without a recursive delete, which is banned.
set -u

SCRIPT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/em-dash-guard.sh"
EM=$'\xe2\x80\x94'
TMP=$(mktemp -d)
PASS=0
TOTAL=0

g() { git -C "$TMP" -c user.email=t@t -c user.name=t -c commit.gpgsign=false "$@"; }

check() {
  desc="$1"; want_exit="$2"; want_msg="$3"; code="$4"; out="$5"
  TOTAL=$((TOTAL + 1))
  if [ "$code" -eq "$want_exit" ] && echo "$out" | grep -qF -- "$want_msg"; then
    PASS=$((PASS + 1)); echo "ok - $desc"
  else
    echo "FAIL - $desc (exit=$code, expected=$want_exit)"; echo "$out"
  fi
}

g init -q -b main
printf 'old %s line\nkeep\n' "$EM" > "$TMP/old.txt"
g add -A; g commit -q -m base
out=$(cd "$TMP" && bash "$SCRIPT" HEAD~1 2>&1); code=$?
check "root commit without a base passes with a message" 0 "HEAD is a root commit" "$code" "$out"

# case <desc> <expected exit> <expected substring> ; the caller has already staged changes
case_run() {
  g add -A; g commit -q -m case
  out=$(cd "$TMP" && bash "$SCRIPT" main 2>&1)
  check "$1" "$2" "$3" "$?" "$out"
  g checkout -q main
}

g checkout -q -b c1
printf 'hello\nworld\n' > "$TMP/a.txt"
case_run "clean diff passes" 0 "em-dash-guard: clean"

g checkout -q -b c2
printf 'hello\nbad %s here\n' "$EM" > "$TMP/a.txt"
case_run "added em dash fails and names file:line" 1 "a.txt:2:"

g checkout -q -b c3
mkdir -p "$TMP/challenge/data"
printf 'x %s y\n' "$EM" > "$TMP/challenge/README.md"
printf 'x %s y\n' "$EM" > "$TMP/challenge/data/README.md"
printf '# x %s y\n' "$EM" > "$TMP/.gitleaksignore"
case_run "em dash in excluded paths passes" 0 "em-dash-guard: clean"

g checkout -q -b c4
printf 'keep\n' > "$TMP/old.txt"
case_run "em dash in a removed line passes" 0 "em-dash-guard: clean"

g checkout -q -b c5
printf 'old %s line\nkeep\nnew clean line\n' "$EM" > "$TMP/old.txt"
case_run "em dash in an unchanged line passes" 0 "em-dash-guard: clean"

g checkout -q -b c6
g mv old.txt moved.txt
case_run "pure rename passes" 0 "em-dash-guard: clean"

g checkout -q -b c7
g mv old.txt moved.txt
printf 'old %s line\nkeep\nadded %s here\n' "$EM" "$EM" > "$TMP/moved.txt"
case_run "rename plus added em dash fails and names the new path" 1 "moved.txt:3:"

# The exempt list is exactly challenge/ at the root and .gitleaksignore; look-alikes are caught.
g checkout -q -b c9
mkdir -p "$TMP/docs/challenge"
printf 'x %s y\n' "$EM" > "$TMP/docs/challenge/README.md"
case_run "em dash in docs/challenge/ is still caught" 1 "docs/challenge/README.md:1:"

g checkout -q -b c10
mkdir -p "$TMP/challenge-notes"
printf 'x %s y\n' "$EM" > "$TMP/challenge-notes/n.md"
case_run "em dash in a prefix look-alike folder is still caught" 1 "challenge-notes/n.md:1:"

g checkout -q -b c11
mkdir -p "$TMP/docs/decisions"
printf 'x %s y\n' "$EM" > "$TMP/docs/decisions/log.md"
case_run "em dash in the decisions log is caught" 1 "docs/decisions/log.md:1:"

g checkout -q -b c12
printf 'x %s y\n' "$EM" > "$TMP/challenge.md"
case_run "em dash in a file named like the folder is caught" 1 "challenge.md:1:"

g checkout -q -b c8
printf 'second\n' > "$TMP/b.txt"; g add -A; g commit -q -m second
out=$(cd "$TMP" && bash "$SCRIPT" no-such-ref 2>&1); code=$?
check "unknown base ref on a non-root commit fails closed" 2 "failed" "$code" "$out"

if [ "$PASS" -eq "$TOTAL" ]; then
  echo "PASS $PASS/$TOTAL"
  exit 0
else
  echo "FAIL $PASS/$TOTAL"
  exit 1
fi
