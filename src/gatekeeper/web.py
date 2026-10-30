"""Local web app: applicant and staff screens over pipeline.handle(), stdlib HTTP only.

    python scripts/serve.py            # http://127.0.0.1:8000
"""
import itertools
import json
import re
import threading
from datetime import datetime, timezone
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from gatekeeper import data, pipeline, planner, query, rules, spe

STATIC = Path(__file__).resolve().parent / "static"
REQUESTS = Path(__file__).resolve().parents[2] / "challenge" / "requests"
FILES = {"/": ("index.html", "text/html; charset=utf-8"),
         "/app.css": ("app.css", "text/css; charset=utf-8"),
         "/app.js": ("app.js", "text/javascript; charset=utf-8")}
CASE_ID = re.compile(r"^[A-Za-z0-9_\-]{1,64}$")
MAX_BODY = 64 * 1024
DECISIONS = {"REJECT", "APPROVE_STATISTICAL", "APPROVE_SPE"}

_cases = {}
_seq = itertools.count(1)
_lock = threading.Lock()


def _now():
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def examples():
    return [json.loads(p.read_text(encoding="utf-8"))
            for p in sorted(REQUESTS.glob("R*.json"))]


def _next_case_id():
    with _lock:
        while (cid := f"C-{next(_seq):03d}") in _cases:
            pass
        return cid


def decide(request):
    if isinstance(request, dict) and not str(request.get("id") or "").strip():
        request = {**request, "id": _next_case_id()}
    result = pipeline.handle(request)
    case = {"request": request, "result": result, "decided_at": _now(),
            "status": "needs review" if result["needs_staff_review"] else "decided automatically",
            "staff_action": None}
    with _lock:
        _cases[request["id"]] = case
    return result


def audit(case_id):
    log = spe.ROOT / case_id / "audit.log"
    if not log.exists():
        return []
    return [json.loads(line) for line in log.read_text(encoding="utf-8").splitlines() if line.strip()]


def case_summary(case_id, case):
    r = case["result"]
    return {"id": case_id, "organisation": case["request"]["applicant"].get("organisation", ""),
            "decision": r["decision"], "needs_staff_review": r["needs_staff_review"],
            "status": case["status"], "decided_at": case["decided_at"],
            "review_note": (r.get("staff") or {}).get("review_note"),
            "staff_action": case["staff_action"]}


class Handler(BaseHTTPRequestHandler):
    server_version = "Gatekeeper"

    def log_message(self, fmt, *args):
        pass

    def _send(self, status, body, ctype="application/json; charset=utf-8"):
        data = body if isinstance(body, bytes) else json.dumps(body, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.end_headers()
        self.wfile.write(data)

    def _error(self, status, message):
        self._send(status, {"error": message})

    def _body(self):
        length = int(self.headers.get("Content-Length") or 0)
        if length > MAX_BODY:
            raise ValueError("The request is too large.")
        try:
            body = json.loads(self.rfile.read(length) or b"{}")
        except json.JSONDecodeError as e:
            raise ValueError(f"The request is not valid JSON: {e.msg} at line {e.lineno}, column {e.colno}.") from e
        if not isinstance(body, dict):
            raise ValueError("The request must be a JSON object.")
        return body

    def _case_id(self, part):
        if not CASE_ID.match(part):
            raise ValueError("Unknown case.")
        return part

    def do_GET(self):
        path = self.path.split("?", 1)[0]
        if path in FILES:
            name, ctype = FILES[path]
            return self._send(HTTPStatus.OK, (STATIC / name).read_bytes(), ctype)
        if path == "/api/examples":
            return self._send(HTTPStatus.OK, examples())
        if path == "/api/hospitals":
            return self._send(HTTPStatus.OK, data.summary())
        if path == "/api/cases":
            with _lock:
                items = [case_summary(k, v) for k, v in _cases.items()]
            items.sort(key=lambda c: (not c["needs_staff_review"], c["decided_at"]), reverse=False)
            return self._send(HTTPStatus.OK, items)
        m = re.fullmatch(r"/api/cases/([^/]+)", path)
        if m:
            try:
                cid = self._case_id(m.group(1))
            except ValueError as e:
                return self._error(HTTPStatus.NOT_FOUND, str(e))
            with _lock:
                case = _cases.get(cid)
            if case is None:
                return self._error(HTTPStatus.NOT_FOUND, "Unknown case.")
            return self._send(HTTPStatus.OK, {**case, "audit": audit(cid)})
        self._error(HTTPStatus.NOT_FOUND, "Not found.")

    def do_POST(self):
        path = self.path.split("?", 1)[0]
        try:
            body = self._body()
        except ValueError as e:
            return self._error(HTTPStatus.BAD_REQUEST, str(e))
        if path == "/api/decide":
            try:
                return self._send(HTTPStatus.OK, decide(body))
            except rules.InvalidRequest as e:
                return self._error(HTTPStatus.UNPROCESSABLE_ENTITY, f"The request could not be read: {e}")
            except (planner.PlanningFailed, query.InvalidPlan) as e:
                return self._error(HTTPStatus.UNPROCESSABLE_ENTITY,
                                   f"The decision was made, but the numbers could not be planned: {e}")
        m = re.fullmatch(r"/api/spe/([^/]+)/download", path)
        if m:
            try:
                cid = self._case_id(m.group(1))
                spe.download(cid, str(body.get("table", "all records"))[:64])
            except spe.DownloadBlocked as e:
                return self._send(HTTPStatus.FORBIDDEN, {"blocked": True, "logged_at": _now(), "reason": str(e)})
            except ValueError as e:
                return self._error(HTTPStatus.NOT_FOUND, str(e))
        m = re.fullmatch(r"/api/cases/([^/]+)/(confirm|overrule)", path)
        if m:
            cid = m.group(1)
            with _lock:
                case = _cases.get(cid) if CASE_ID.match(cid) else None
                if case is None:
                    return self._error(HTTPStatus.NOT_FOUND, "Unknown case.")
                if m.group(2) == "confirm":
                    case["staff_action"] = {"action": "confirmed", "at": _now()}
                else:
                    decision, reason = body.get("decision"), str(body.get("reason", "")).strip()
                    if decision not in DECISIONS or not reason:
                        return self._error(HTTPStatus.BAD_REQUEST,
                                           "Choose a decision and give a reason for overruling.")
                    case["staff_action"] = {"action": "overruled", "decision": decision,
                                            "reason": reason[:2000], "at": _now()}
                case["status"] = "reviewed"
                return self._send(HTTPStatus.OK, case_summary(cid, case))
        self._error(HTTPStatus.NOT_FOUND, "Not found.")


def serve(host="127.0.0.1", port=8000):
    httpd = ThreadingHTTPServer((host, port), Handler)
    print(f"Gatekeeper running at http://{host}:{port}")
    httpd.serve_forever()
