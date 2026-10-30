"""Deterministic decision rules in the brief's order (Art. 54, then request type, then Art. 66)."""
import re

REQUEST = "health data request"
APPLICATION = "health data access application"
REQUIRED_FIELDS = ("id", "applicant", "requested_as", "purpose", "question", "definitions")

ART54_TEXT = {
    "a": "decisions detrimental to natural persons (Art. 54(a))",
    "b": "decisions on jobs, insurance, credit or other discrimination (Art. 54(b))",
    "c": "advertising or marketing (Art. 54(c))",
    "d": "developing products that may harm individuals or public health, such as tobacco and nicotine products (Art. 54(d))",
    "e": "activities in conflict with national ethics law (Art. 54(e))",
}


class InvalidRequest(ValueError):
    pass


def blocked_by_53_2(reading):
    """Art. 53(2): a purpose that fits only public health, policy-making or official statistics needs a public
    body, or a third party processing on its behalf."""
    return (bool(reading.get("reserved_purpose_only")) and not reading.get("public_body")
            and not reading.get("acts_for_public_body"))


TABLE_PATTERN = r"\bper\b|%|percent|proportion|\bshare\b|\bmean\b|average"


def report_is_table(definitions):
    """Art. 66(3) second limb: a 'Report ...' line that asks for counts, percentages or means per group."""
    report = next((d for d in definitions if isinstance(d, str) and re.match(r"report\b", d, re.I)), None)
    return bool(report and re.search(TABLE_PATTERN, report, re.I))


def validate(request):
    missing = [f for f in REQUIRED_FIELDS if f not in request]
    if missing:
        raise InvalidRequest(f"request is missing fields: {', '.join(missing)}")
    if request["requested_as"] not in (REQUEST, APPLICATION):
        raise InvalidRequest(
            f"requested_as must be '{REQUEST}' or '{APPLICATION}', got '{request['requested_as']}'"
        )
    if not isinstance(request["definitions"], list):
        raise InvalidRequest("definitions must be a list of strings")


def decide(request, reading):
    """reading: {"prohibited", "art54_point", "justifies_records", "evidence", "needs_staff_review"}."""
    validate(request)
    evidence = reading.get("evidence") or ""
    review = bool(reading.get("needs_staff_review"))

    if reading["prohibited"]:
        what = ART54_TEXT.get(reading.get("art54_point") or "", "a use prohibited by Art. 54")
        return _result("REJECT", ["54"], 1, review, evidence,
                       f"The stated purpose amounts to {what}. Access is refused (Art. 54); "
                       "a refusal is always justified to the applicant (Art. 68(9)).")

    if blocked_by_53_2(reading):
        return _result("REJECT", ["53"], 1, True, evidence,
                       "The stated purpose fits only public health, policy-making or official statistics "
                       "(Art. 53(1), points (a) to (c)). Access for those purposes is reserved for public "
                       "sector bodies and Union bodies (Art. 53(2)); the applicant is not one, so no allowed "
                       "purpose remains and access is refused (Art. 53). A refusal is always justified to the "
                       "applicant (Art. 68(9)); a reframed application under another purpose may be submitted.")

    result = _allowed(request, reading, review, evidence)
    if reading.get("acts_for_public_body") and reading.get("reserved_purpose_only") and not reading.get("public_body"):
        result["needs_staff_review"] = True
        result["reason"] += (" The applicant states it acts on behalf of a public sector body (Art. 53(2)); "
                             "staff must verify the mandate before release.")
    return result


def _allowed(request, reading, review, evidence):
    if request["requested_as"] == REQUEST:
        return _result("APPROVE_STATISTICAL", ["53", "69"], 2, review, evidence,
                       "The purpose is allowed (Art. 53). A health data request is answered "
                       "only with anonymised statistics; the applicant never sees the data (Art. 69).")

    if reading["justifies_records"] and report_is_table(request["definitions"]):
        return _result("APPROVE_STATISTICAL", ["53", "66", "69"], 4, review, evidence,
                       "The purpose is allowed (Art. 53). The application explains a need for records, but "
                       "what it asks to report is counts, percentages or means per group, which anonymised "
                       "statistics answer, so pseudonymised records are not necessary (Art. 66(2)). It is "
                       "answered with anonymised statistics instead (Art. 68(3), Art. 69).")

    if reading["justifies_records"]:
        return _result("APPROVE_SPE", ["53", "66", "68", "73"], 3, review, evidence,
                       "The purpose is allowed (Art. 53). The applicant has shown that anonymised data "
                       "cannot achieve it, so pseudonymised data is justified (Art. 66(3)). Access only "
                       "under a data permit (Art. 68) inside a secure processing environment; only "
                       "non-personal data may leave it (Art. 73(2)).")

    return _result("APPROVE_STATISTICAL", ["53", "66", "69"], 4, review, evidence,
                   "The purpose is allowed (Art. 53). The application does not show why anonymised "
                   "statistics are not enough, so pseudonymised records are not justified (Art. 66(2)). "
                   "It is answered with anonymised statistics instead (Art. 68(3), Art. 69).")


def _result(decision, articles, rule, review, evidence, reason):
    return {
        "decision": decision,
        "articles": articles,
        "rule": rule,
        "reason": reason,
        "evidence": evidence,
        "needs_staff_review": review,
    }
