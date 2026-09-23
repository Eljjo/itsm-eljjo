# ai-generated: 90% - Claude Code drafted the package; I reviewed the SLA algorithm against API.md's test vectors.
"""Test-clock handling (API.md section 8) and RFC 3339 parsing/formatting."""
import os
from datetime import datetime, timezone

from fastapi import HTTPException, Request


def parse_instant(value: str) -> datetime:
    """Parse an RFC 3339 instant into an aware UTC datetime. Raises ValueError if malformed."""
    text = value.strip()
    if text.endswith("Z") or text.endswith("z"):
        text = text[:-1] + "+00:00"
    dt = datetime.fromisoformat(text)
    if dt.tzinfo is None:
        raise ValueError(f"instant has no timezone offset: {value!r}")
    return dt.astimezone(timezone.utc)


def to_iso(dt: datetime) -> str:
    """Format an aware datetime as a whole-second UTC instant with a Z suffix."""
    return dt.astimezone(timezone.utc).replace(microsecond=0).strftime("%Y-%m-%dT%H:%M:%SZ")


def _test_clock_enabled() -> bool:
    return os.environ.get("SVCDESK_TEST_CLOCK", "").strip().lower() in ("1", "true")


def resolve_now(request: Request) -> datetime:
    """Resolve "now" for a single request: the X-Test-Clock header when enabled, else real UTC time."""
    if _test_clock_enabled():
        header = request.headers.get("X-Test-Clock")
        if header:
            try:
                return parse_instant(header)
            except ValueError:
                raise HTTPException(
                    status_code=422,
                    detail={
                        "error": {
                            "code": "validation",
                            "message": "X-Test-Clock is not a valid RFC 3339 instant",
                        }
                    },
                )
    return datetime.now(timezone.utc)
