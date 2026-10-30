"""The web layer: examples, decisions, the blocked download and staff actions over real HTTP."""
import json
import threading
import urllib.error
import urllib.request
from http.server import ThreadingHTTPServer

import pytest

from gatekeeper import web


@pytest.fixture(scope="module")
def base():
    httpd = ThreadingHTTPServer(("127.0.0.1", 0), web.Handler)
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    yield f"http://127.0.0.1:{httpd.server_address[1]}"
    httpd.shutdown()


def call(base, path, body=None):
    data = None if body is None else (body if isinstance(body, bytes) else json.dumps(body).encode())
    req = urllib.request.Request(base + path, data=data, headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req) as res:
            return res.status, res.read()
    except urllib.error.HTTPError as e:
        return e.code, e.read()


def example(base, rid):
    _, raw = call(base, "/api/examples")
    return next(r for r in json.loads(raw) if r["id"] == rid)


def test_pages_and_examples(base):
    status, html = call(base, "/")
    assert status == 200 and b"Datenzugang" in html
    for path in ("/app.css", "/app.js"):
        assert call(base, path)[0] == 200
    _, raw = call(base, "/api/examples")
    assert [r["id"] for r in json.loads(raw)] == [f"R{i:02d}" for i in range(1, 11)]
    assert call(base, "/../AGENTS.md")[0] == 404


def test_decide_three_outcomes(base):
    decisions = {}
    for rid in ("R02", "R03", "R05"):
        status, raw = call(base, "/api/decide", example(base, rid))
        assert status == 200
        decisions[rid] = json.loads(raw)["decision"]
    assert decisions == {"R02": "REJECT", "R03": "APPROVE_STATISTICAL", "R05": "APPROVE_SPE"}


def test_download_is_refused_and_logged(base):
    call(base, "/api/decide", example(base, "R05"))
    status, raw = call(base, "/api/spe/R05/download", {"table": "all records"})
    assert status == 403 and json.loads(raw)["blocked"] is True
    _, case = call(base, "/api/cases/R05")
    assert json.loads(case)["audit"][-1]["result"] == "blocked"
    assert call(base, "/api/spe/..%2F..%2Fx/download", {})[0] == 404


def test_bad_input_is_explained(base):
    status, raw = call(base, "/api/decide", b"{not json")
    assert status == 400 and "not valid JSON" in json.loads(raw)["error"]
    status, raw = call(base, "/api/decide", {"id": "X1"})
    assert status == 422 and json.loads(raw)["error"].startswith("The request could not be read")


def test_staff_confirm_and_overrule(base):
    call(base, "/api/decide", example(base, "R09"))
    _, raw = call(base, "/api/cases")
    assert "R09" in {c["id"] for c in json.loads(raw)}
    assert call(base, "/api/cases/R09/overrule", {"decision": "APPROVE_SPE"})[0] == 400
    status, raw = call(base, "/api/cases/R09/overrule", {"decision": "APPROVE_SPE", "reason": "Checked by hand."})
    assert status == 200 and json.loads(raw)["staff_action"]["action"] == "overruled"
    assert call(base, "/api/cases/R09/confirm", {})[0] == 200
    assert call(base, "/api/cases/NOPE/confirm", {})[0] == 404


def test_hospitals_endpoint_returns_totals_only(base):
    status, raw = call(base, "/api/hospitals")
    assert status == 200
    rows = json.loads(raw)
    assert len(rows) == 3
    assert all(set(r) == {"hospital", "patients", "opted_out_excluded", "records"} for r in rows)
