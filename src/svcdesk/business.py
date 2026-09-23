# ai-generated: 90% - Claude Code drafted the package; I reviewed the SLA algorithm against API.md's test vectors.
"""Priority, SLA clocks and the state machine.

The three module-level constants C1, C2 and C3 fix the resolutions defended in DECISIONS.md and specs/001-svcdesk
(specs/001-svcdesk/spec.md section 6): this is the single place that encodes which side of each contradiction the
running service exhibits.
"""
from datetime import date, datetime, time as dtime, timedelta, timezone
from zoneinfo import ZoneInfo

from fastapi import HTTPException

from svcdesk.clock import parse_instant, to_iso

# The three decisions (see DECISIONS.md and specs/001-svcdesk/spec.md section 6).
C1 = "wallclock"   # SLA clock for P1: "wallclock" | "business"
C2 = "immutable"   # closed tickets and reopening: "reopen" | "immutable"
C3 = "vip"         # VIP reporters and the priority matrix: "matrix" | "vip"

WARSAW = ZoneInfo("Europe/Warsaw")
BUSINESS_OPEN = dtime(8, 0, 0)
BUSINESS_CLOSE = dtime(16, 0, 0)

PRIORITY_MATRIX = {
    (1, 1): "P1", (1, 2): "P2", (1, 3): "P3",
    (2, 1): "P2", (2, 2): "P3", (2, 3): "P4",
    (3, 1): "P3", (3, 2): "P4", (3, 3): "P4",
}

SLA_TARGETS = {
    "P1": (timedelta(minutes=15), timedelta(hours=4)),
    "P2": (timedelta(hours=1), timedelta(hours=8)),
    "P3": (timedelta(hours=4), timedelta(hours=24)),
    "P4": (timedelta(hours=8), timedelta(hours=72)),
}


def compute_priority(impact: int, urgency: int, vip: bool) -> str:
    base = PRIORITY_MATRIX[(impact, urgency)]
    if C3 == "vip" and vip and base in ("P3", "P4"):
        return "P2"
    return base


def clock_kind_for(priority: str) -> str:
    """Which clock (wallclock|business) this priority's SLA targets run on, under C1."""
    if C1 == "wallclock" and priority == "P1":
        return "wallclock"
    return "business"


def _next_business_day(d: date) -> date:
    d = d + timedelta(days=1)
    while d.weekday() >= 5:
        d = d + timedelta(days=1)
    return d


def _business_open_at_or_after(local: datetime) -> datetime:
    """The earliest instant at or after `local` that lies inside a Warsaw business window."""
    d = local.date()
    cur = local
    while True:
        if d.weekday() < 5:
            open_dt = datetime.combine(d, BUSINESS_OPEN, tzinfo=WARSAW)
            close_dt = datetime.combine(d, BUSINESS_CLOSE, tzinfo=WARSAW)
            if cur < open_dt:
                return open_dt
            if cur < close_dt:
                return cur
        d = d + timedelta(days=1)
        cur = datetime.combine(d, dtime(0, 0, 0), tzinfo=WARSAW)


def business_due(created_at: datetime, target: timedelta) -> datetime:
    """The due instant (UTC) for `target` consumed from consecutive Warsaw business windows.

    The tie rule: a target that is exactly used up at closing time is due at closing time that
    day, not at opening the next business day (API.md section 4).
    """
    cur = _business_open_at_or_after(created_at.astimezone(WARSAW))
    remaining = target
    while True:
        close_dt = datetime.combine(cur.date(), BUSINESS_CLOSE, tzinfo=WARSAW)
        available = close_dt - cur
        if remaining <= available:
            return (cur + remaining).astimezone(timezone.utc)
        remaining -= available
        nd = _next_business_day(cur.date())
        cur = datetime.combine(nd, BUSINESS_OPEN, tzinfo=WARSAW)


def wallclock_due(created_at: datetime, target: timedelta) -> datetime:
    return (created_at + target).astimezone(timezone.utc)


def sla_due_instants(priority: str, created_at: datetime) -> tuple[datetime, datetime]:
    ack_target, resolve_target = SLA_TARGETS[priority]
    if clock_kind_for(priority) == "wallclock":
        return wallclock_due(created_at, ack_target), wallclock_due(created_at, resolve_target)
    return business_due(created_at, ack_target), business_due(created_at, resolve_target)


def within_business_window(now: datetime) -> bool:
    local = now.astimezone(WARSAW)
    if local.weekday() >= 5:
        return False
    return BUSINESS_OPEN <= local.time() < BUSINESS_CLOSE


def compute_sla_view(ticket: dict, now: datetime) -> dict:
    priority = ticket["priority"]
    clock_kind = clock_kind_for(priority)
    ack_due = parse_instant(ticket["sla"]["ack_due_at"])
    resolve_due = parse_instant(ticket["sla"]["resolve_due_at"])

    if ticket["acknowledged_at"]:
        ack_breached = parse_instant(ticket["acknowledged_at"]) > ack_due
    else:
        ack_breached = now > ack_due

    if ticket["resolved_at"]:
        resolve_breached = parse_instant(ticket["resolved_at"]) > resolve_due
    else:
        resolve_breached = now > resolve_due

    paused = (
        ticket["state"] not in ("resolved", "closed")
        and clock_kind == "business"
        and not within_business_window(now)
    )

    return {
        "priority": priority,
        "ack_due_at": ticket["sla"]["ack_due_at"],
        "resolve_due_at": ticket["sla"]["resolve_due_at"],
        "ack_breached": ack_breached,
        "resolve_breached": resolve_breached,
        "paused": paused,
    }


_ACTION_FROM = {"ack": "new", "start": "acknowledged", "resolve": "in_progress", "close": "resolved"}
_ACTION_TO = {"ack": "acknowledged", "start": "in_progress", "resolve": "resolved", "close": "closed"}
_ACTION_FIELD = {"ack": "acknowledged_at", "start": None, "resolve": "resolved_at", "close": "closed_at"}


def _conflict(action: str, state: str) -> HTTPException:
    return HTTPException(
        status_code=409,
        detail={"error": {"code": "invalid_transition", "message": f"cannot {action} a ticket in state {state}"}},
    )


def apply_transition(ticket: dict, action: str, now: datetime) -> None:
    if action == "reopen":
        _apply_reopen(ticket, now)
        return

    from_state = _ACTION_FROM[action]
    if ticket["state"] != from_state:
        raise _conflict(action, ticket["state"])

    ticket["state"] = _ACTION_TO[action]
    field = _ACTION_FIELD[action]
    if field:
        ticket[field] = to_iso(now)


def _apply_reopen(ticket: dict, now: datetime) -> None:
    state = ticket["state"]
    if state == "resolved":
        deadline = parse_instant(ticket["resolved_at"])
    elif state == "closed":
        if C2 != "reopen":
            raise HTTPException(
                status_code=409,
                detail={"error": {"code": "ticket_closed", "message": "closed tickets are immutable"}},
            )
        deadline = parse_instant(ticket["closed_at"])
    else:
        raise _conflict("reopen", state)

    if now > deadline + timedelta(days=7):
        raise HTTPException(
            status_code=409,
            detail={"error": {"code": "reopen_window_expired", "message": "reopen window has expired"}},
        )

    ticket["state"] = "in_progress"
    ticket["resolved_at"] = None
    ticket["closed_at"] = None
