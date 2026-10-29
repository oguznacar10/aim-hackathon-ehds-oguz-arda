"""Sanity check of the vendored challenge fixture the build leans on."""
import csv
import json
from pathlib import Path

CHALLENGE = Path(__file__).resolve().parent.parent / "challenge"
DECISIONS = {"REJECT", "APPROVE_STATISTICAL", "APPROVE_SPE"}


def test_expected_answer_key():
    expected = json.loads((CHALLENGE / "requests" / "expected.json").read_text(encoding="utf-8"))
    ids = [f"R{n:02d}" for n in range(1, 11)]
    assert set(ids) <= expected.keys()
    for rid in ids:
        assert expected[rid]["decision"] in DECISIONS, rid
        assert isinstance(expected[rid]["articles"], list), rid


def test_patients_csv_counts():
    with open(CHALLENGE / "data" / "patients.csv", encoding="utf-8", newline="") as f:
        # Plain ints only: pytest prints the operands of a failing assert, and rows must never reach test output.
        total = opted_out = 0
        for row in csv.DictReader(f):
            total += 1
            opted_out += row["opted_out"] == "true"
    assert total == 20000
    assert opted_out == 839
