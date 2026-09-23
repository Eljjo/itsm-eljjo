<!-- ai-generated: 70% - Claude Code drafted this specification from REQUIREMENTS.md and API.md; I picked the three
     conflict resolutions (C1/C2/C3), reviewed the derivation of the business-hours algorithm and edited the
     wording of the "why" for each conflict before committing. -->

# svcdesk specification (Lab 1)

Written before any code under `src/`, per the course rule "specs before code" (L1-CORE-5). This document restates
the contract of [REQUIREMENTS.md](../../doc/lab1/REQUIREMENTS.md) and [API.md](../../doc/lab1/API.md) as the
specification this implementation will satisfy, and it fixes the three points where the requirements document
contradicts itself, so that the code that follows has one unambiguous target.

## 1. Purpose and scope

`svcdesk` is an HTTP JSON API (R-01) for a ~400-person service desk across three offices. It creates and tracks
tickets, computes their priority from an impact/urgency matrix, drives them through a fixed state machine, and
reports SLA due instants, breach and pause status, so that a Monday-morning report can be produced from one
`GET /tickets/{id}/sla` call per ticket (R-15). Scope for Lab 1: everything in REQUIREMENTS.md R-01 to R-25 and
API.md sections 1-10. Out of scope for Lab 1: authentication, pagination, `related_to` validation, holiday
calendars.

## 2. Ticket model and priority (R-03, R-04, R-05, R-06)

A ticket carries a title (1-200 chars, required), an optional description (0-4000 chars), a reporter
(name 1-100 chars required, optional email, optional `vip` flag defaulting to false), an impact (1-3) and an
urgency (1-3). Priority is computed, never accepted from a client, from the matrix in API.md §3:

| impact \ urgency | 1 | 2 | 3 |
|---|---|---|---|
| **1** | P1 | P2 | P3 |
| **2** | P2 | P3 | P4 |
| **3** | P3 | P4 | P4 |

## 3. State machine (R-07, R-08, R-09)

`new -> acknowledged -> in_progress -> resolved -> closed`, one endpoint per transition
(`ack`, `start`, `resolve`, `close`, `reopen`). Any other transition is `409` with a JSON `error` body; an action
on an unknown id is `404`. A closed ticket does not accept `ack`/`start`/`resolve`/`close` again; further work
after closure is a new ticket referencing the old one via `related_to`.

## 4. SLA (R-12, R-13, R-14, R-15, R-16)

Each priority has an acknowledge and a resolve target, measured from `created_at` (API.md §4 table). A target is
turned into a due instant on one of two clocks:

- **wall-clock**: `created_at + target`, ignoring business hours entirely.
- **business-hours**: only Mon-Fri 08:00-16:00 Europe/Warsaw counts; a target that lands exactly on 16:00 is due
  at 16:00 that day, not 08:00 the next (the tie rule, API.md §4).

`GET /tickets/{id}/sla` reports both due instants, `ack_breached`, `resolve_breached` and `paused`, evaluated at
`now` (API.md §5). Equality at the due instant is not a breach (R-16).

## 5. Test clock (R-21, API.md §8)

When `SVCDESK_TEST_CLOCK` is `1`/`true`, a request may carry `X-Test-Clock` (an RFC 3339 instant) that is `now`
for that request only; no cross-request ordering is enforced. A header that fails to parse is `400`/`422`.

## 6. The three contradictions

REQUIREMENTS.md contains three pairs of requirements that cannot both hold in full. Each is resolved here by
rejecting the minimal conflicting part of one requirement and keeping everything else; both sides remain tested
(CHECKS.md accepts either value, but only one is what this service actually does). The full defence of each
choice — decision, rejected alternative, reason, service owner, customer outcome — lives in
[DECISIONS.md](../../DECISIONS.md); this section only fixes which value this specification commits the code to,
so that `src/` has one target from the first line written.

### C1 — SLA clock for P1

R-13 says every SLA clock pauses outside business hours. R-14 says P1 must be acknowledged and resolved "around
the clock: a P1 raised on Friday evening is late at 15 minutes past, not on Monday morning" — which only holds if
P1's clock never pauses. The two cannot both be literally true for P1.

**This specification fixes C1 = `wallclock`.** P1's ack and resolve targets are `created_at + target`, unpaused,
exactly as R-14 states in its own worked example. P2 through P4 keep the business-hours clock of R-13. The part of
R-13 given up is its claim to apply to *every* priority without exception.

### C2 — Closed tickets and reopening

R-09 says "a closed ticket is immutable." R-10 says a reporter may reopen a ticket that is "resolved or closed"
within 7 days. Read together for a closed ticket, one says the state can never change again and the other says it
can, within a week.

**This specification fixes C2 = `immutable`.** `POST /tickets/{id}/reopen` succeeds only from `resolved`, within
7 days of `resolved_at`; from `closed` it always answers `409`, regardless of age, and R-09's own remedy applies —
a new ticket referencing the old one via `related_to`. The part of R-10 given up is the word "closed" in "resolved
or closed."

### C3 — VIP reporters and the priority matrix

R-05 says priority "is derived from the impact and urgency matrix and from nothing else." R-06 says a VIP
reporter's ticket is "never lower than P2, whatever the matrix says." A VIP ticket at impact 3/urgency 3 (matrix
value P4) cannot satisfy both sentences at once.

**This specification fixes C3 = `vip`.** The matrix computes a base priority; if the reporter is VIP and that
base priority is P3 or P4, the served priority is raised to P2. P1 and P2 tickets are unaffected by the VIP flag.
The part of R-05 given up is "and from nothing else" — for VIP reporters, the flag is a second input.

## 7. Non-functional (R-17 to R-25)

UTC `Z` instants throughout; opaque server-assigned ids; `GET /tickets` supports exact-match `state`/`priority`
filters with no pagination; unrecognised or server-owned request fields are ignored, never rejected; the service
builds from the repository (no `image:`-only service), needs no network once built, uses no host bind mounts, and
answers `/health` within 120 s of `docker compose up`.
