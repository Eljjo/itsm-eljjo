# svcdesk (Lab 1)

This repository holds the `svcdesk` service-desk API for the ITSM 2026/27 course. The requirements document
(`doc/lab1/REQUIREMENTS.md`) deliberately contains three contradictory pairs of requirements; the resolutions
this service exhibits are fixed in `DECISIONS.md` and `specs/001-svcdesk/spec.md` section 6 (C1 = `wallclock`,
C2 = `immutable`, C3 = `vip`). Do not change those three values without updating both files together and without
the running service actually matching the new values — L1-CORE-4 fails the moment they disagree.

## Layout

- `specs/` — the specification, written and committed before any code under `src/`.
- `src/svcdesk/` — the FastAPI implementation: `models.py` (request validation), `business.py` (priority, SLA
  clocks, the state machine — the module that encodes C1/C2/C3), `storage.py` (SQLite-backed), `main.py` (routes).
- `src/tests/run.py` — Stretch S3: our own suite against the running service, run via
  `docker compose --profile tests run --rm --build tests`.
- `DECISIONS.md` — the reasoning artifact graded by the lecturer.

## Working in this repository

- `./itsmlab.sh verify 1` runs the full published check suite (Core + Stretch) against the compose stack; run it
  after any change to `src/`, `docker-compose.yml` or `Dockerfile`.
- Every file under `src/` and `specs/`, plus `DECISIONS.md`, needs the `ai-generated: <0-100>% - <how>` header in
  its first ten lines (course rule, checked as an advisory).
- No network access at container start; dependencies are installed at build time only (`requirements.txt`,
  installed in the `Dockerfile`).
- No host bind mounts in `docker-compose.yml`; only named volumes.

## Agents

`.claude/agents/reviewer.md` is a review-only sub-agent scoped by `AGENT-POLICY.md`: it may read and comment on
this repository, but its `disallowedTools` list blocks it from running Docker, from pushing or force-pushing git
history, and from deleting files — those remain actions a human takes deliberately, never a side effect of asking
for a review.
