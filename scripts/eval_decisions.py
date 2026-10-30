"""Scores the decision pipeline: the 10 challenge requests and, optionally, a red-team set.

    python scripts/eval_decisions.py                  # 10 challenge requests, 3 runs
    python scripts/eval_decisions.py --set holdout    # red-team exam set (redteam/holdout)
    python scripts/eval_decisions.py --mode all --no-cache --runs N   # ablation, live LLM calls

Modes: rules = keyword reader + rules (offline); hybrid = LLM reads, rules decide (shipped path);
llm = the model decides end to end; all = the three side by side.
"""
import argparse
import json
import sys
import time
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "src"))

from gatekeeper import direct, llm, reader, rules  # noqa: E402

EXTRA_OK = {"67", "71"}
MODES = ("rules", "hybrid", "llm")


def decide(req, mode, cache, provider=None):
    if mode == "llm":
        return direct.decide(req, provider=provider, cache=cache)
    reading = reader.read(req, provider=provider, mode="keywords" if mode == "rules" else "auto",
                          cache=cache)
    return {**rules.decide(req, reading), "source": reading["source"]}


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
    ap.add_argument("--mode", default="hybrid", choices=MODES + ("all",))
    ap.add_argument("--provider", choices=sorted(llm.KEY_ENV),
                    help="which configured key to use; default: the first one found")
    ap.add_argument("--no-cache", action="store_true",
                    help="call the LLM every run instead of reusing cached readings")
    args = ap.parse_args()

    cases = load(args.set)
    if not cases:
        raise SystemExit(f"no cases in set '{args.set}'")
    modes = MODES if args.mode == "all" else (args.mode,)
    summary = {mode: run_mode(mode, cases, args) for mode in modes}
    if len(modes) > 1:
        print(f"{'mode':<8} {'correct':<9} {'consistent':<11} slowest")
        for mode, (correct, consistent, slowest) in summary.items():
            print(f"{mode:<8} {correct:<2}/{len(cases):<6} {consistent:<2}/{len(cases):<8} {slowest:.2f} s")
    return 0 if all(c == len(cases) for c, _, _ in summary.values()) else 1


def run_mode(mode, cases, args):
    runs, slowest = [], 0.0
    for _ in range(args.runs):
        outcome = {}
        for req, exp_decision, exp_articles in cases:
            t0 = time.perf_counter()
            result = decide(req, mode, cache=not args.no_cache, provider=args.provider)
            slowest = max(slowest, time.perf_counter() - t0)
            ok = result["decision"] == exp_decision and (
                exp_articles is None or articles_ok(result["articles"], exp_articles))
            outcome[req["id"]] = (result["decision"], result["articles"], ok,
                                  result["needs_staff_review"], result["source"])
        runs.append(outcome)

    first = runs[0]
    source = next(iter(first.values()))[4]
    print(f"mode={mode} set={args.set} cases={len(cases)} runs={args.runs} source={source} "
          f"cache={'off' if args.no_cache else 'on'}")
    for rid, (decision, arts, ok, review, _) in first.items():
        flag = " [staff review]" if review else ""
        print(f"  {rid:<10} {decision:<20} {','.join(arts):<14} {'ok' if ok else 'WRONG'}{flag}")
    correct = sum(ok for _, _, ok, _, _ in first.values())
    consistent = sum(len({json.dumps(r[rid][:2]) for r in runs}) == 1 for rid in first)
    print(f"correct decisions: {correct}/{len(cases)}")
    print(f"consistent over {args.runs} runs: {consistent}/{len(cases)}")
    print(f"slowest decision: {slowest:.2f} s")
    return correct, consistent, slowest


if __name__ == "__main__":
    sys.exit(main())
