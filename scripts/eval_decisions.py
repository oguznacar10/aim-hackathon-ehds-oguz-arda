"""Scores the decision pipeline: the 10 challenge requests and, optionally, a red-team set.

    python scripts/eval_decisions.py                  # 10 challenge requests, 3 runs
    python scripts/eval_decisions.py --set holdout    # red-team exam set (redteam/holdout)
"""
import argparse
import json
import sys
import time
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "src"))

from gatekeeper import reader, rules  # noqa: E402

EXTRA_OK = {"67", "71"}


def articles_ok(ours, expected):
    ours, expected = set(ours), set(expected)
    return expected <= ours and ours - expected <= EXTRA_OK


def load(set_name):
    if set_name == "challenge":
        req_dir = REPO / "challenge" / "requests"
        expected = json.loads((req_dir / "expected.json").read_text(encoding="utf-8"))
        return [(json.loads((req_dir / f"{rid}.json").read_text(encoding="utf-8")),
                 expected[rid]["decision"], expected[rid]["articles"]) for rid in sorted(expected)]
    cases = []
    for path in sorted((REPO / "redteam" / set_name).glob("*.json")):
        req = json.loads(path.read_text(encoding="utf-8"))
        cases.append((req, req["expected"], None))
    return cases


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--set", default="challenge", help="challenge, tuning or holdout")
    ap.add_argument("--runs", type=int, default=3)
    args = ap.parse_args()

    cases = load(args.set)
    if not cases:
        raise SystemExit(f"no cases in set '{args.set}'")
    runs, slowest = [], 0.0
    for _ in range(args.runs):
        outcome = {}
        for req, exp_decision, exp_articles in cases:
            t0 = time.perf_counter()
            result = rules.decide(req, reader.read(req))
            slowest = max(slowest, time.perf_counter() - t0)
            ok = result["decision"] == exp_decision and (
                exp_articles is None or articles_ok(result["articles"], exp_articles))
            outcome[req["id"]] = (result["decision"], result["articles"], ok, result["needs_staff_review"])
        runs.append(outcome)

    first = runs[0]
    source = reader.read(cases[0][0])["source"]
    print(f"set={args.set} cases={len(cases)} runs={args.runs} reader={source}")
    for rid, (decision, arts, ok, review) in first.items():
        flag = " [staff review]" if review else ""
        print(f"  {rid:<10} {decision:<20} {','.join(arts):<14} {'ok' if ok else 'WRONG'}{flag}")
    correct = sum(ok for _, _, ok, _ in first.values())
    consistent = sum(len({json.dumps(r[rid][:2]) for r in runs}) == 1 for rid in first)
    print(f"correct decisions: {correct}/{len(cases)}")
    print(f"consistent over {args.runs} runs: {consistent}/{len(cases)}")
    print(f"slowest decision: {slowest:.2f} s")
    return 0 if correct == len(cases) else 1


if __name__ == "__main__":
    sys.exit(main())
