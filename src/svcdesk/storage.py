# ai-generated: 90% - Claude Code drafted the package; I reviewed the SLA algorithm against API.md's test vectors.
"""SQLite-backed ticket storage: an in-memory index backed by a durable log, so tickets survive a
restart of the container (R-23) without paying a JSON round-trip on every read."""
import json
import os
import sqlite3
import threading
from typing import Optional


class Storage:
    def __init__(self, path: str):
        os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
        self._lock = threading.Lock()
        self._conn = sqlite3.connect(path, check_same_thread=False)
        self._conn.execute("CREATE TABLE IF NOT EXISTS tickets (id TEXT PRIMARY KEY, data TEXT NOT NULL)")
        self._conn.commit()
        self._tickets: dict[str, dict] = {}
        for (data,) in self._conn.execute("SELECT data FROM tickets"):
            ticket = json.loads(data)
            self._tickets[ticket["id"]] = ticket

    def create(self, ticket: dict) -> None:
        with self._lock:
            self._tickets[ticket["id"]] = ticket
            self._conn.execute(
                "INSERT INTO tickets (id, data) VALUES (?, ?)", (ticket["id"], json.dumps(ticket))
            )
            self._conn.commit()

    def update(self, ticket: dict) -> None:
        with self._lock:
            self._tickets[ticket["id"]] = ticket
            self._conn.execute(
                "UPDATE tickets SET data = ? WHERE id = ?", (json.dumps(ticket), ticket["id"])
            )
            self._conn.commit()

    def get(self, ticket_id: str) -> Optional[dict]:
        with self._lock:
            ticket = self._tickets.get(ticket_id)
            return dict(ticket) if ticket is not None else None

    def list(self, state: Optional[str] = None, priority: Optional[str] = None) -> list[dict]:
        with self._lock:
            tickets = list(self._tickets.values())
        if state is not None:
            tickets = [t for t in tickets if t["state"] == state]
        if priority is not None:
            tickets = [t for t in tickets if t["priority"] == priority]
        return [dict(t) for t in tickets]
