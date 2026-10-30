"""Deterministic decision rules in the brief's order (Art. 54, then request type, then Art. 66)."""

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

    if request["requested_as"] == REQUEST:
        return _result("APPROVE_STATISTICAL", ["53", "69"], 2, review, evidence,
                       "The purpose is allowed (Art. 53). A health data request is answered "
                       "only with anonymised statistics; the applicant never sees the data (Art. 69).")

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
