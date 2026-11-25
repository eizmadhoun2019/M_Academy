# Masheed_Academy

**Status:** Active H1.5 foundation (documentation baseline established 2026-11-22; charter 2.4)
**Repository:** `https://github.com/eizmadhoun2019/M_Academy` — own history, no legacy imports.
The legacy `Masheed-Academy` repository and its running deployment are reference only and must
stay untouched.
**Owner:** Project owner (see `RULES.md` → Authority)
**Documentation standard:** UPDS 1.0.0-rc2

## What is this?
Masheed Academy is an independent, multi-company corporate learning platform: publish video
courses, assign them to companies, departments or people, enforce sequential learning with
**server-verified** progress, notify learners and managers, and report completion.

It runs standalone: its own public site (`/`), its own accounts and sessions, its own database,
mail and permissions. Masheed is the first company, not the only company the architecture
supports. The Hub integration is retained but **dormant and optional** (`docs/hub-contract.md`);
nothing on the launch path depends on it.

## Main capabilities (H1.5 target)
- Company, department, user and membership model with server-side active-company context.
- Local authentication: email verification, password reset, invitations, sessions, TOTP MFA.
- Dynamic scoped RBAC: platform / company / department / self, default roles and exceptional
  grants, last-admin protection.
- Course authoring with immutable published versions (≥2 sections, ≥2 lessons).
- Direct-to-storage upload, ffmpeg→HLS processing, short-lived playback URLs.
- Assignment to company / department / member, due date, mandatory flag.
- Server-authoritative heartbeat progress, forward-skip rejection, completion threshold,
  sequential locking.
- Reminders at due−3 / due / due+1 and a manager digest at due+3, per company time zone and
  language, idempotent.
- Company reports and CSV export; audited platform summary.
- Append-only audit trail and privacy export/anonymization tooling.
- Bilingual Arabic/English UI with RTL/LTR, accessible states and no raw UUIDs.

## Getting started
### Prerequisites
Python 3.12+, Docker with Compose plugin, Make.

### Setup
```bash
cp .env.example .env            # PowerShell: Copy-Item .env.example .env
docker compose -p m-academy up -d --build --wait
docker compose -p m-academy exec -T web python manage.py migrate
docker compose -p m-academy --profile setup run --rm createbuckets
```
Verify: `http://localhost:8101/healthz` → HTTP 200. Tests: `make test` (PostgreSQL, in-memory
mail, eager Celery). Documentation: `python scripts/check_docs.py`.

The stack is its own: compose project `m-academy`, own containers, PostgreSQL, Redis, MinIO
buckets, volumes, secrets and ports. It runs beside the legacy deployment without sharing
anything. Names, ports, buckets and safety rules are in
[environment isolation](docs/operations/environments.md).

## Read in this order (new developer or agent)
1. [Rules](RULES.md) — authority, priorities, the «كمل» protocol, gates, stop conditions.
2. [Charter](CHARTER.md) — vision, H1.5 scope, REQ-01…REQ-28, success measures.
3. [Architecture](ARCHITECTURE.md) — current vs target, modules, tenancy, identity, security,
   ADRs.
4. [Status](STATUS.md) and [Plan](docs/plan.md) — what is done, what is next, acceptance criteria.
5. [Decisions](docs/decisions.md) — every D-NNN and whether it is in force.
6. [Traceability](docs/traceability.md) — IDs, gates G1–G12, sources of truth.

## Canonical specifications (read before implementing)
- [Domain model](docs/domain-model.md) — entities, constraints, state machines, progress algorithm
- [Access control](docs/access-control.md) — permission catalogue, roles, scopes, enforcement
- [Security](docs/security.md) — controls, PII register, retention, incidents
- [API](docs/api.md) — routes, error codes, capabilities per route
- [Configuration](docs/configuration.md) — settings, storage, HLS, pagination, throttles
- [UI screens](docs/ui/screen-specification.md) · [wireframes](docs/ui/wireframes.md)
- [Notifications](docs/notifications.md) · [Reports](docs/reports.md)
- [Background jobs](docs/background-jobs.md) — task catalogue and per-company schedule
- [Migration H1.5](docs/migration-h1.5.md) — legacy mapping, cutover, rollback
- [Operations](docs/operations/environments.md) — environments, deploy, backup, alerts
- [Performance profile](docs/performance-profile.yaml) — capacity and NFR targets
- [Hub contract](docs/hub-contract.md) — optional integration, currently dormant
- [ADR index](docs/adr/README.md) · [Skills](SKILLS.md) · [History](LOG.md)

## Contributing
Follow [RULES.md](RULES.md). One approved task or checkpoint at a time from
[docs/plan.md](docs/plan.md); tests with every change; only affected documents updated;
`LOG.md` appended. Do not merge to `main` without the owner's approval.

## License
Proprietary — internal company use until decided otherwise (see CHARTER → Constraints).
