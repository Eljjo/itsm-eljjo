# ai-generated: 90% - Claude Code drafted the package; I reviewed the SLA algorithm against API.md's test vectors.
"""Request models. Server-owned fields (id, priority, state, timestamps, sla) and unknown fields are
silently ignored (R-20, API.md section 2): every model below leaves pydantic's default "ignore" extras
behaviour in place rather than forbidding them."""
from typing import Literal, Optional

from pydantic import BaseModel, Field


class Reporter(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    email: Optional[str] = None
    vip: bool = False


class TicketCreate(BaseModel):
    title: str = Field(min_length=1, max_length=200)
    description: str = Field(default="", max_length=4000)
    reporter: Reporter
    impact: Literal[1, 2, 3]
    urgency: Literal[1, 2, 3]
    related_to: Optional[str] = None
