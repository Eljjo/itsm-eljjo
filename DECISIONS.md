---
svcdesk_decisions:
  C1: wallclock      # wallclock | business
  C2: immutable      # reopen | immutable
  C3: vip            # matrix | vip
---
<!-- ai-generated: 60% - Claude Code drafted the reasoning from REQUIREMENTS.md and API.md against the decisions
     I picked; I edited the service-owner framing and the customer-outcome wording before committing. -->

# Decisions

## C1 - SLA clock for P1

**Decision:** P1 tickets use the wall-clock target for both acknowledgement and resolution: 15 minutes and 4
hours from `created_at`, counted around the clock, nights and weekends included. P2 through P4 keep the
business-hours clock unchanged.

**Rejected alternative:** Business-hours for every priority including P1, so that a P1 raised at 17:00 on a
Friday would not be due until well into the following Monday.

**Reason:** R-14 is explicit and gives its own worked example: "a P1 raised on Friday evening is late at 15
minutes past, not on Monday morning." That sentence only makes sense if P1's clock never pauses, which
contradicts the blanket pause rule of R-13. Since P1 is by definition the case where the whole organisation has
stopped working (impact 1, urgency 1), it is the one priority where "pause outside business hours" defeats the
purpose of having an SLA at all: the outage does not pause because the office closes.

**Service owner:** The on-call incident manager, because they are the one paged at 17:05 on a Friday and the one
whose response time this target actually measures; a P1 clock that pauses overnight would silently hide a missed
page from the person accountable for catching it.

**Customer outcome:** An organisation-wide outage gets a real, continuous 15-minute/4-hour promise regardless of
when it happens, instead of a promise that quietly stops counting from 16:00 Friday to 08:00 Monday while the
outage continues uninterrupted.

## C2 - Closed tickets and reopening

**Decision:** `POST /tickets/{id}/reopen` succeeds only from the `resolved` state, within 7 days of
`resolved_at`. From `closed`, reopen always answers `409`, regardless of how recently the ticket was closed; a
new issue against the same problem becomes a new ticket with `related_to` pointing at the closed one.

**Rejected alternative:** Allowing reopen from `closed` as well, within the same 7-day window measured from
`closed_at`.

**Reason:** R-09 states plainly that "a closed ticket is immutable" and gives the remedy itself: "any further
work on the same issue requires a new ticket." Closing is a distinct, reporter-confirmed action, separate from
resolving; treating it as reversible collapses that distinction and means `closed` no longer means what R-09
says it means. R-10's "resolved or closed" is kept only for the `resolved` half, which is the state where no
confirmation has happened yet and a reopen is genuinely a continuation of the same unresolved work.

**Service owner:** The service-desk process owner, because immutability of `closed` is what lets the desk's
reporting trust that a closed count is final for the reporting period it closed in, rather than something that
can retroactively change the numbers a manager already saw.

**Customer outcome:** A reporter who confirms a fix worked, then later finds the same symptom back, files a new
ticket that is explicitly linked to the history (`related_to`) rather than silently reopening old data; the
audit trail says exactly when the original issue was closed and when a related one began, instead of one ticket
whose closed timestamp no longer means "done."

## C3 - VIP reporters and the priority matrix

**Decision:** The priority matrix computes a base priority from impact and urgency. If the reporter is VIP
(`reporter.vip = true`) and that base priority is P3 or P4, the served priority is raised to P2. VIP tickets that
are already P1 or P2 by the matrix are unaffected.

**Rejected alternative:** Priority derived from the matrix alone in every case, with `reporter.vip` stored but
never changing the computed value (a VIP reporter with a cosmetic, single-person issue stays P4).

**Reason:** R-06 states the business rule directly and gives its own justification: VIP tickets are "never lower
than P2... so that executive issues are visible to the desk immediately." That guarantee is meaningless if it
never actually overrides the matrix, so it must apply exactly where the matrix alone would produce P3 or P4.
R-05's "and from nothing else" is kept for every reporter who is not VIP, and even for VIP reporters at P1/P2,
where the matrix and the VIP floor already agree.

**Service owner:** The service desk manager, because deciding whose issues jump the queue ahead of the matrix is
an escalation-policy call with staffing and fairness consequences, not something the ticket schema should decide
implicitly.

**Customer outcome:** A VIP reporter's low-impact request still gets seen inside a P2 window instead of waiting
behind three days of P4 work, at the cost of that reporter's cosmetic issues consuming P2 capacity that would
otherwise go to a non-VIP ticket of genuinely equal severity — a trade-off the desk makes deliberately and
visibly, not by accident of the matrix.
