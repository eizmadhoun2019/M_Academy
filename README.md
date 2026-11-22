# Masheed_Academy

**Status:** Active (rebuild from scratch — documentation baseline established 2026-11-22)
**Repository:** `https://github.com/eizmadhoun2019/M_Academy` — own history, no legacy
imports. The legacy `Masheed-Academy` repository and its running deployment are reference
only and must stay untouched.
**Owner:** Project owner (see RULES.md → Authority)
**Documentation standard:** UPDS 1.0.0-rc2

## What is this?
A centralized employee-training module: upload video courses, assign them to people,
departments or roles, enforce sequential learning with **server-verified** progress,
and notify managers automatically. Delivered inside Masheed Hub as an internal module
(Horizon 1), architected so it can be detached and productized later (Horizons 2–3).

Academy is a standalone Django and PostgreSQL service on its own server. Masheed Hub
(reverse proxy + identity) is integrated over HTTPS per `docs/hub-contract.md`
(proposed). Local development uses `host_stub`.

## Main capabilities
- Course authoring with immutable published versions (≥2 sections, ≥2 lessons).
- Direct-to-storage video upload, automatic ffmpeg→HLS processing, presigned playback.
- Assignment to user / department / role with due date and mandatory flag; auto-enroll
  on department/role join via the `member_changed` hook.
- Server-authoritative heartbeat progress: forward skipping rejected, completion at ≥90%
  watched (configurable); sequential lesson locking.
- Reminders at due−3 / due / due+1, manager escalation digest at due+3; idempotent.
- Manager dashboard: completion rate, overdue list, average time, CSV export.
- Academy-managed permission grants on top of Hub role defaults (grants-only mode available).
- Append-only audit trail; privacy export/anonymization tooling.

## Getting started
### Prerequisites
- Python 3.12+, Docker with Compose plugin, Make.

### Setup
```bash
cp .env.example .env            # PowerShell: Copy-Item .env.example .env
docker compose -p m-academy up -d --build --wait
docker compose -p m-academy exec -T web python manage.py migrate
docker compose -p m-academy exec -T web python manage.py ensure_development_storage
```
Verify: `http://localhost:8101/healthz` → HTTP 200. Test profile: `make test`
(uses PostgreSQL, in-memory email, eager Celery).

The stack is its own: compose project `m-academy`, own containers, PostgreSQL, Redis,
MinIO buckets, volumes, secrets and ports. It runs beside the legacy deployment without
sharing anything, so it never uses port 8001 (the legacy web) or 9000/9001 (the legacy
MinIO). Names, ports and buckets are fixed in
[environment isolation](docs/operations/environments.md).

## Project documentation
- [Rules](RULES.md) — binding working rules and authority
- [Current status](STATUS.md) — state, active work, next action
- [Charter](CHARTER.md) — purpose, scope, requirements, success criteria
- [Architecture](ARCHITECTURE.md) — current and approved design
- [History](LOG.md) — append-only event log
- [Skills index](SKILLS.md) — repeatable procedures

Build specifications (canonical — read before implementing):
- [Domain model](docs/domain-model.md) — entities, fields, constraints, state machines,
  progress/anti-skip algorithm
- [API inventory](docs/api.md) — endpoints, capabilities, error codes
- [Decision register](docs/decisions.md) — every `D-NNN` and its current value
- [Traceability](docs/traceability.md) — ID scheme, legacy mapping, CI gates G1–G9,
  sources of truth

Supporting requirements references:
- [Proposed Hub integration contract](docs/hub-contract.md)
- [UI wireframes](docs/ui/wireframes.md) · visual baseline: `docs/ui/reference/masheed-academy-screens.pdf`
- [Performance profile](docs/performance-profile.yaml)
- [Configuration](docs/configuration.md) — settings, upload policy, HLS, pagination,
  throttles
- [Background jobs](docs/background-jobs.md) — Celery task catalogue and schedule
- [Notifications](docs/notifications.md) — triggers, Arabic/English copy, channels
- [Reports](docs/reports.md) — metric definitions, columns, CSV format
- [Environment isolation](docs/operations/environments.md) — repository, stack names,
  ports, buckets, cookies and the safety rules
- [ADR index](docs/adr/README.md)

## Contributing
Follow [RULES.md](RULES.md). One approved task at a time from STATUS.md, tests with every
change, documents updated before finishing, LOG.md entry appended.

## License
Proprietary — internal company use until decided otherwise (see CHARTER → Constraints).
