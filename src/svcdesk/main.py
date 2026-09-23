# ai-generated: 90% - Claude Code drafted the package; I reviewed the SLA algorithm against API.md's test vectors.
"""svcdesk HTTP API (API.md). All bodies are JSON; validation errors and not-found errors carry a
top-level "error" object (R-20, R-25)."""
import os
import uuid

from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from svcdesk.business import apply_transition, compute_priority, compute_sla_view, sla_due_instants
from svcdesk.clock import resolve_now, to_iso
from svcdesk.models import TicketCreate
from svcdesk.storage import Storage

DB_PATH = os.environ.get("SVCDESK_DB", "/data/svcdesk.db")

app = FastAPI(title="svcdesk")
storage = Storage(DB_PATH)


@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):
    content = exc.detail if isinstance(exc.detail, dict) else {"error": {"code": "error", "message": str(exc.detail)}}
    return JSONResponse(status_code=exc.status_code, content=content)


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    return JSONResponse(
        status_code=422,
        content={"error": {"code": "validation", "message": "request body failed validation"}},
    )


@app.get("/health")
def health():
    return {"status": "ok", "service": "svcdesk"}


def _not_found() -> HTTPException:
    return HTTPException(status_code=404, detail={"error": {"code": "not_found", "message": "ticket not found"}})


def _build_ticket(payload: TicketCreate, now) -> dict:
    priority = compute_priority(payload.impact, payload.urgency, payload.reporter.vip)
    ack_due, resolve_due = sla_due_instants(priority, now)
    return {
        "id": str(uuid.uuid4()),
        "title": payload.title,
        "description": payload.description or "",
        "reporter": {
            "name": payload.reporter.name,
            "email": payload.reporter.email,
            "vip": payload.reporter.vip,
        },
        "impact": payload.impact,
        "urgency": payload.urgency,
        "priority": priority,
        "state": "new",
        "created_at": to_iso(now),
        "acknowledged_at": None,
        "resolved_at": None,
        "closed_at": None,
        "related_to": payload.related_to,
        "sla": {"ack_due_at": to_iso(ack_due), "resolve_due_at": to_iso(resolve_due)},
    }


@app.post("/tickets", status_code=201)
def create_ticket(payload: TicketCreate, request: Request):
    now = resolve_now(request)
    ticket = _build_ticket(payload, now)
    storage.create(ticket)
    return ticket


@app.get("/tickets")
def list_tickets(state: str | None = None, priority: str | None = None):
    return storage.list(state=state, priority=priority)


@app.get("/tickets/{ticket_id}")
def get_ticket(ticket_id: str):
    ticket = storage.get(ticket_id)
    if ticket is None:
        raise _not_found()
    return ticket


@app.get("/tickets/{ticket_id}/sla")
def get_sla(ticket_id: str, request: Request):
    ticket = storage.get(ticket_id)
    if ticket is None:
        raise _not_found()
    now = resolve_now(request)
    return compute_sla_view(ticket, now)


def _make_transition_handler(action: str):
    def handler(ticket_id: str, request: Request):
        ticket = storage.get(ticket_id)
        if ticket is None:
            raise _not_found()
        now = resolve_now(request)
        apply_transition(ticket, action, now)
        storage.update(ticket)
        return ticket

    handler.__name__ = f"{action}_ticket"
    return handler


for _action in ("ack", "start", "resolve", "close", "reopen"):
    app.post(f"/tickets/{{ticket_id}}/{_action}")(_make_transition_handler(_action))
