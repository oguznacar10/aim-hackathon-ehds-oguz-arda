"""Generated requests are kept only when every code exists in the data and the shape matches the originals."""
import json
from pathlib import Path

import pytest

from gatekeeper import redteam

REPO = Path(__file__).resolve().parent.parent
REQUESTS = REPO / "challenge" / "requests"
VOCAB = redteam.vocabulary()


def load(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def test_vocabulary_comes_from_the_data_files():
    assert len(VOCAB["loinc"]) == 4
    assert all(code.startswith(("4548", "39156", "8480", "62238")) for code, _ in VOCAB["loinc"])
    assert len(VOCAB["regions"]) == 9
    assert len(VOCAB["data_holders"]) == 3


@pytest.mark.parametrize("rid", [f"R{i:02d}" for i in range(1, 11)])
def test_every_original_request_passes(rid):
    assert redteam.validate_generated(load(REQUESTS / f"{rid}.json"), VOCAB) == []


def test_generated_request_with_unknown_code_is_rejected():
    req = load(REPO / "redteam" / "tuning" / "Gde652cfe.json")
    problems = redteam.validate_generated(req, VOCAB)
    assert any("G89" in p for p in problems)
    assert any("requested_format" in p for p in problems)


def test_wrong_format_for_request_type_is_rejected():
    req = {**load(REQUESTS / "R01.json"), "requested_format": "pseudonymised records"}
    assert redteam.validate_generated(req, VOCAB) == [
        "requested_format must be 'anonymised statistics' for a health data request"]


def test_prompt_lists_only_real_codes():
    text = redteam.vocabulary_text(VOCAB)
    assert "4548-4" in text and "31 December 2025" in text
    assert "G89" not in text
