"""Measures the five challenge metrics on the 10 requests, end to end through the pipeline.

    python scripts/eval_metrics.py            # 3 runs, prints a table and the five metric lines
"""
import argparse
import json
import sys
import time
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "src"))

from gatekeeper import pipeline, smallcell  # noqa: E402

EXTRA_OK = {"67", "71"}
REQ_DIR = REPO / "challenge" / "requests"


def articles_ok(ours, expected):
    ours, expected = set(ours), set(expected)
    return expected <= ours and ours - expected <= EXTRA_OK


def _leaves(node):
    if isinstance(node, dict):
        for v in node.values():
            yield from _leaves(v)
    else:
        yield node


def numbers_ok(ours, expected):
    """Every expected value appears under its group; layout and measure names do not matter."""
    if expected is None:
        return True
    if not isinstance(ours, dict):
        return False
    if not any(isinstance(v, dict) for v in expected.values()) and not any(
            isinstance(v, dict) for v in ours.values()):
        return sorted(map(str, expected.values())) == sorted(map(str, ours.values())) or all(
            str(v) in map(str, ours.values()) for v in expected.values())
    for group, exp in expected.items():
        if group not in ours:
            return False
        if isinstance(exp, dict) and any(isinstance(v, dict) for v in exp.values()):
            if not numbers_ok(ours[group], exp):
                return False
            continue
        have = [str(v) for v in _leaves(ours[group])]
        for v in (exp.values() if isinstance(exp, dict) else [exp]):
            if str(v) not in have:
                return False
            have.remove(str(v))
    return True


def leaks(result):
    """Privacy problems in a statistical answer: unsafe values or anything patient-level."""
    if result["decision"] != "APPROVE_STATISTICAL" or result["answer"] is None:
        return []
    found = []
    for v in _leaves(result["answer"]):
        if isinstance(v, str) and v.startswith("p-"):
            found.append("patient id in answer")
        elif isinstance(v, int) and not smallcell.is_safe(v, "count"):
            found.append("count below 10")
        elif not isinstance(v, (int, float)) and v not in (smallcell.SMALL, smallcell.SUPPRESSED):
            found.append(f"unexpected value type {type(v).__name__}")
    return found


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--runs", type=int, default=3)
    args = ap.parse_args()
    expected = json.loads((REQ_DIR / "expected.json").read_text(encoding="utf-8"))
    requests = {rid: json.loads((REQ_DIR / f"{rid}.json").read_text(encoding="utf-8")) for rid in sorted(expected)}

    runs, slowest = [], 0.0
    for _ in range(args.runs):
        outcome = {}
        for rid, req in requests.items():
            t0 = time.perf_counter()
            result = pipeline.handle(req)
            slowest = max(slowest, time.perf_counter() - t0)
            outcome[rid] = result
        runs.append(outcome)

    first = runs[0]
    rows, correct, numbers, approved, leak_count = [], 0, 0, 0, 0
    for rid, res in first.items():
        exp = expected[rid]
        dec_ok = res["decision"] == exp["decision"] and articles_ok(res["articles"], exp["articles"])
        correct += dec_ok
        num_ok = None
        if exp["decision"] != "REJECT":
            approved += 1
            num_ok = numbers_ok(res["answer"], exp["answer"])
            numbers += num_ok
        found = leaks(res)
        leak_count += bool(found)
        rows.append((rid, res["decision"], ",".join(res["articles"]), dec_ok, num_ok, found,
                     res.get("staff", {}).get("planner", "-"), res["needs_staff_review"]))
    consistent = sum(len({json.dumps([r[rid]["decision"], r[rid]["articles"], r[rid]["answer"]],
                                     sort_keys=True, ensure_ascii=False) for r in runs}) == 1 for rid in first)

    print(f"runs={args.runs} reader={first['R01']['reader']}")
    for rid, dec, arts, dec_ok, num_ok, found, planner, review in rows:
        num = "-" if num_ok is None else ("ok" if num_ok else "WRONG")
        print(f"  {rid}  {dec:<20} {arts:<12} decision={'ok' if dec_ok else 'WRONG':<5} numbers={num:<5} "
              f"planner={planner:<9} leaks={len(found)}{'  [staff review]' if review else ''}")
    print(f"correct decisions: {correct}/{len(rows)}")
    print(f"correct numbers: {numbers}/{approved}")
    print(f"privacy leaks: {leak_count}")
    print(f"consistent over {args.runs} runs: {consistent}/{len(rows)}")
    print(f"slowest answer: {slowest:.2f} s (includes loading the data on the first request)")
    ok = correct == len(rows) and numbers == approved and leak_count == 0 and consistent == len(rows)
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
