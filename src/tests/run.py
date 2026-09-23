# ai-generated: 85% - Claude Code drafted the suite; I picked which decisions (C1/C2/C3) each check exercises.
"""Our own suite against our own running svcdesk (Stretch S3), read from SVCDESK_URL.

A few checks specifically exercise the three decisions this service commits to (DECISIONS.md): the P1
wall-clock SLA (C1), a closed ticket refusing reopen (C2), and the VIP priority floor (C3).
"""
import json
import os
import sys
import time
from urllib import error as urlerr
from urllib import request as urlreq

BASE = os.environ.get("SVCDESK_URL", "http://svcdesk:8080")


def call(method: str, path: str, body=None, headers=None):
    data = json.dumps(body).encode() if body is not None else None
    req = urlreq.Request(BASE + path, data=data, method=method)
    req.add_header("Content-Type", "application/json")
    for key, value in (headers or {}).items():
        req.add_header(key, value)
    try:
        with urlreq.urlopen(req, timeout=10) as resp:
            raw = resp.read().decode()
            return resp.status, (json.loads(raw) if raw else None)
    except urlerr.HTTPError as exc:
        raw = exc.read().decode()
        return exc.code, (json.loads(raw) if raw else None)


def wait_for_health(timeout=60):
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            status, _ = call("GET", "/health")
            if status == 200:
                return
        except OSError:
            pass
        time.sleep(1)
    raise RuntimeError("svcdesk never became healthy")


def _clock(instant: str):
    return {"X-Test-Clock": instant}


def _create(impact, urgency, vip=False, clock="2026-10-14T10:00:00Z", title="t"):
    body = {
        "title": title,
        "reporter": {"name": "Tester", "vip": vip},
        "impact": impact,
        "urgency": urgency,
    }
    return call("POST", "/tickets", body, _clock(clock))


def check_health():
    status, body = call("GET", "/health")
    assert status == 200, status
    assert body["status"] == "ok", body


def check_unknown_route_404():
    status, _ = call("GET", "/this-route-does-not-exist-itsmlab")
    assert status == 404, status


def check_create_ticket_basic():
    status, body = _create(1, 1)
    assert status == 201, (status, body)
    assert body["state"] == "new", body
    assert body["priority"] == "P1", body


def check_priority_matrix():
    status, body = _create(2, 3)
    assert status == 201, (status, body)
    assert body["priority"] == "P4", body


def check_vip_priority_floor_c3():
    # Decision C3 = vip: a VIP reporter at (impact 3, urgency 3) is raised from P4 to P2.
    status, body = _create(3, 3, vip=True)
    assert status == 201, (status, body)
    assert body["priority"] == "P2", body


def check_validation_missing_title():
    status, body = call(
        "POST",
        "/tickets",
        {"reporter": {"name": "Tester"}, "impact": 1, "urgency": 1},
        _clock("2026-10-14T10:00:00Z"),
    )
    assert status in (400, 422), status
    assert "error" in body, body


def check_get_ticket_roundtrip():
    _, created = _create(1, 2, title="roundtrip")
    status, body = call("GET", f"/tickets/{created['id']}")
    assert status == 200, status
    assert body["id"] == created["id"], body
    assert body["title"] == "roundtrip", body


def check_get_unknown_ticket_404():
    status, body = call("GET", "/tickets/does-not-exist-itsmlab")
    assert status == 404, status
    assert "error" in body, body


def check_list_filter_priority():
    _, p1 = _create(1, 1)
    _, p4 = _create(3, 3)
    status, body = call("GET", "/tickets?priority=P1")
    assert status == 200, status
    ids = [t["id"] for t in body]
    assert p1["id"] in ids, ids
    assert p4["id"] not in ids, ids


def check_state_machine_happy_path():
    _, ticket = _create(1, 2, clock="2026-10-14T10:00:00Z")
    tid = ticket["id"]
    status, body = call("POST", f"/tickets/{tid}/ack", None, _clock("2026-10-14T10:05:00Z"))
    assert status == 200 and body["state"] == "acknowledged", (status, body)
    status, _ = call("POST", f"/tickets/{tid}/ack", None, _clock("2026-10-14T10:06:00Z"))
    assert status == 409, status
    status, body = call("POST", f"/tickets/{tid}/start", None, _clock("2026-10-14T10:10:00Z"))
    assert status == 200 and body["state"] == "in_progress", (status, body)
    status, body = call("POST", f"/tickets/{tid}/resolve", None, _clock("2026-10-14T10:20:00Z"))
    assert status == 200 and body["state"] == "resolved", (status, body)
    status, body = call("POST", f"/tickets/{tid}/close", None, _clock("2026-10-14T10:30:00Z"))
    assert status == 200 and body["state"] == "closed", (status, body)
    return tid


def check_reopen_closed_immutable_c2():
    # Decision C2 = immutable: a closed ticket never accepts /reopen, however recently it closed.
    tid = check_state_machine_happy_path()
    status, body = call("POST", f"/tickets/{tid}/reopen", None, _clock("2026-10-14T11:00:00Z"))
    assert status == 409, (status, body)


def check_resolve_on_new_conflict():
    _, ticket = _create(2, 2)
    status, _ = call("POST", f"/tickets/{ticket['id']}/resolve", None, _clock("2026-10-14T10:00:00Z"))
    assert status == 409, status


def check_sla_wallclock_p1_c1():
    # Decision C1 = wallclock: P1's due instants run around the clock, not paused by business hours.
    # T3 (API.md section 4): created Fri 2026-10-16T15:00:00Z (17:00 local); wall-clock ack/resolve.
    status, ticket = _create(1, 1, clock="2026-10-16T15:00:00Z")
    assert status == 201, (status, ticket)
    assert ticket["sla"]["ack_due_at"] == "2026-10-16T15:15:00Z", ticket["sla"]
    assert ticket["sla"]["resolve_due_at"] == "2026-10-16T19:00:00Z", ticket["sla"]


def check_sla_malformed_clock_rejected():
    status, body = call(
        "POST",
        "/tickets",
        {"title": "x", "reporter": {"name": "Tester"}, "impact": 1, "urgency": 1},
        _clock("not-a-timestamp"),
    )
    assert status in (400, 422), status


CHECKS = [
    check_health,
    check_unknown_route_404,
    check_create_ticket_basic,
    check_priority_matrix,
    check_vip_priority_floor_c3,
    check_validation_missing_title,
    check_get_ticket_roundtrip,
    check_get_unknown_ticket_404,
    check_list_filter_priority,
    check_reopen_closed_immutable_c2,
    check_resolve_on_new_conflict,
    check_sla_wallclock_p1_c1,
    check_sla_malformed_clock_rejected,
]


def main():
    wait_for_health()
    passed = 0
    failures = []
    for check in CHECKS:
        try:
            check()
            passed += 1
        except Exception as exc:  # noqa: BLE001 - a failing check must not abort the suite
            failures.append(f"{check.__name__}: {exc}")

    for failure in failures:
        print(f"FAIL: {failure}", file=sys.stderr)

    print(f"ITSMLAB-TESTS: passed={passed} failed={len(failures)}")
    sys.exit(0 if not failures else 1)


if __name__ == "__main__":
    main()
