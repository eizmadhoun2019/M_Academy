# ENVIRONMENTS — Infrastructure, Deployment, Backup and Operations

**Status:** Canonical. `ARCHITECTURE.md` §9 and `README.md` defer to this file.
**Last updated:** 2026-11-25
**Owner decision:** D-023 Confirmed (2026-11-22) — the repository stays public; the baseline is published.

This file makes the isolation rule enforceable and defines the minimum operational baseline. The
new project runs as a **separate stack** next to the legacy `Masheed-Academy` deployment on the
same host, sharing nothing: not a network, volume, database, cache, bucket, credential or port.

---

## 1. Environments
| Environment | Purpose | Data | Mail | Access | Status |
|---|---|---|---|---|---|
| **development** | local work, `docker compose -p m-academy` | disposable, seeded | MailHog (`127.0.0.1:8126`) | loopback only | exists |
| **test** | CI and local test runs | ephemeral database, no real PII | `locmem` | CI only | exists |
| **staging** | release candidate, pilot, restore/alert drills | anonymized or pilot data; never a copy of production PII without approval | SMTP sandbox or a dedicated sending identity | owner + pilot admins, HTTPS, basic auth/IP allowlist | **created in T-034** |
| **production** | live service | real company data | SMTP | HTTPS, least privilege | **only after the owner release decision** |

A feature is “done” in development, “verified” on staging, and “released” only when the owner
accepts GATE-1 and the production decision. Documentation never substitutes for a drill.

## 2. Repository
| Item | Value |
|---|---|
| Repository | `https://github.com/eizmadhoun2019/M_Academy` |
| Default branch | `main` |
| Task branches | `task/<T-NNN>-<slug>` (RULES) |
| Local workspace | this directory — its own git repository, `origin` = `M_Academy` |
| Legacy repository | `Masheed-Academy` — reference only, never a remote, never cloned into this tree |

Rules:
- This repository has its **own history**. No legacy commit, tag, branch, image tag or credential
  is imported. The first commit is the documentation baseline.
- The legacy repository and its deployment stay alive and unmodified. Reading it for context is
  allowed; copying from it is not — anything reused is re-derived from these documents and
  re-implemented here.
- Publication is authorized: the repository is public (D-023 Confirmed). Everything pushed is
  world-readable, so secrets never enter a tracked file.

## 3. Stack identity
| Item | Value | Must not collide with |
|---|---|---|
| Compose project | `m-academy` | `masheed-academy` (legacy, running) |
| Compose files | `docker-compose.yml` (+ `docker-compose.override.yml` if needed) | — |
| Network | `m-academy_default` (compose-managed) | `masheed-academy_default` |
| Container names | `m-academy-{web,db,redis,minio,worker,beat,mailhog}-1` | `masheed-academy-*` |
| Local image tags | `m-academy-web:dev`, `m-academy-worker:dev` | legacy image names |
| Env file | `.env` (untracked) + `.env.example` (tracked, no secrets) | legacy `.env` |

Always pass the project name explicitly so a mistyped `down` can never reach another stack:

```bash
docker compose -p m-academy up -d --build --wait
docker compose -p m-academy ps
```

## 4. Host ports (verified free on 2026-11-22)
The legacy stack holds `8001` (web), `9000`/`9001` (MinIO) and `8026` (MailHog) on 127.0.0.1;
other local projects hold `8000`, `8025`, `15432`, `16379`, `16380`. The values below are
reserved for this project.

| Service | Host binding | Container port | Note |
|---|---|---|---|
| web (Django) | `127.0.0.1:8101` | 8000 | `/healthz`, dev UI |
| PostgreSQL | `127.0.0.1:5433` | 5432 | separate instance and volume |
| Redis | `127.0.0.1:6390` | 6379 | separate instance and volume |
| MinIO API | `127.0.0.1:9100` | 9000 | presigned URLs in dev point here |
| MinIO console | `127.0.0.1:9101` | 9001 | |
| MailHog UI | `127.0.0.1:8126` | 8025 | |
| MailHog SMTP | `127.0.0.1:1126` | 1025 | |

- Bind to `127.0.0.1` only. Never publish on `0.0.0.0`.
- A port change is a documentation change: edit this table in the same task.
- Staging and production use the platform's ingress on 443; no database/Redis/storage port is
  published publicly.

## 5. Data isolation and browser state
| Concern | This project | Never |
|---|---|---|
| PostgreSQL cluster | container `m-academy-db-1`, volume `m-academy_pgdata`, database `academy`, role `academy` | connect to the legacy database or reuse its volume |
| Redis | container `m-academy-redis-1`, volume `m-academy_redisdata` | reuse the legacy Redis instance |
| Redis DB indexes | `0` cache (key prefix `macademy:`, includes `org:<id>:` segments), `1` Celery broker, `2` results | assume another project's DB index |
| Object storage | container `m-academy-minio-1`, volume `m-academy_miniodata`, buckets `academy-media-dev`, `academy-media-test` | reuse a legacy bucket |
| Media working directory | volume `m-academy_media` | share a host folder with the legacy worker |
| Celery queues | `default`, `media`, `notifications` | point a worker at another project's broker |
| Secrets | freshly generated at T-001: `DJANGO_SECRET_KEY`, DB password, MinIO keys, SMTP credentials, (Hub keys only if enabled) | copy any legacy key |
| Email | MailHog in dev; SMTP in staging/production; Hub adapter only when enabled | use the legacy MailHog container |

Browsers scope cookies by **host, not port**, so `localhost:8001` (legacy) and `localhost:8101`
(this project) share a cookie jar.

| Item | Value |
|---|---|
| Django session cookie | `m_academy_sessionid` |
| CSRF cookie | `academy_csrftoken`, `Path=/` (proxy mode: `/academy/`) |
| Storage prefix inside a bucket | `org/<organization_id>/...` |

Never use a bare `sessionid` or `csrftoken` name: it would collide with the legacy app and other
local Django projects.

## 6. Coexistence and safety rules
**Allowed:** `docker compose -p m-academy …` on this project only; reading `docker ps`/`docker
logs` for diagnosis; stopping only `m-academy-*` containers that this project started.

**Prohibited** (also in RULES → AI agent permissions):
- `docker system prune`, `docker volume prune`, `docker network prune`, `docker rm -f`,
  `docker image prune -a` — each can destroy another project's data or images.
- `docker compose down` without `-p m-academy`, or run in another project's directory.
- Stopping, restarting, recreating or editing `masheed-academy-*` containers, its volumes,
  network or compose file.
- Dropping, restoring or migrating any database other than `m-academy-db-1`.

Resource note: both stacks run at once, so media worker concurrency is `1` in development and
exactly one `m-academy-beat-1` runs at a time.

## 7. Configuration and secrets
- Configuration is environment variables read by `config.settings` (`docs/configuration.md`);
  no secret has a default in code.
- `.env` is untracked and excluded from the image. Staging/production read secrets from the
  platform secret store; rotating a secret is a deploy, not a code change.
- Required production values: `DJANGO_SECRET_KEY`, `ACADEMY_ALLOWED_HOSTS`,
  `ACADEMY_CSRF_TRUSTED_ORIGINS`, `ACADEMY_PUBLIC_BASE_URL`, database URL, Redis URL,
  storage credentials/bucket, SMTP host/port/user/password/from, `ACADEMY_ENV=production`,
  `DEBUG=false`.
- Forbidden in production: `ACADEMY_DEVELOPMENT_LOGIN=true`, `DEBUG=true`, wildcard allowed hosts,
  console mail transport, default/blank secrets. Startup fails closed (T-027 test).
- Hub variables are **not** required in standalone mode; setting `ACADEMY_HUB_ENABLED=true`
  requires its full key set (T-033).

## 8. CI/CD
| Stage | What runs | Blocks |
|---|---|---|
| `lint` | ruff format/check, mypy | merge |
| `test` | pytest with PostgreSQL/Redis services, coverage G3 | merge |
| `schema` | `makemigrations --check`, migrate forward/back, OpenAPI build | merge |
| `security` | bandit, pip-audit, image scan, `check --deploy` | merge on high/critical |
| `docs` | `scripts/check_docs.py`, link/ID checks | merge |
| `e2e` | Playwright + axe against a built app (from T-034) | merge on journey/a11y failure |
| `build` | one image tagged with the commit SHA; SBOM | deploy |
| `deploy-staging` | migrate, collectstatic, rolling restart, `/healthz` gate, smoke | promote |
| `deploy-production` | manual owner approval, same image digest, migrate, rolling restart, smoke | release |

Rules: build once, promote the same digest; no build step on the production host; migrations run
before the new code serves, and every migration is backward-compatible for one release (expand →
deploy → contract). A failed health gate triggers automatic rollback to the previous digest.
Secrets come from the environment, never from CI logs; deployment logs record the commit, image
digest and migration list.

## 9. Health, logging and observability
- `GET /healthz` (liveness: process + DB + Redis) and `GET /readyz` (migrations applied, cache
  reachable, storage reachable). Both are unauthenticated but expose no version or secret.
- Structured JSON logs to stdout: timestamp, level, logger, request_id, user_id (UUID, never
  email), organization_id, route template, status, duration. No body, token, password or media
  URL with a signature.
- `X-Request-ID` is accepted only from a trusted proxy, otherwise generated; it is returned and
  logged, and propagated to Celery tasks.
- Metrics (T-034): request count/latency by route template and status, DB pool, queue depth,
  heartbeat latency, mail failures, reminder counts, backup age. Tracing is optional in H1.5;
  if enabled, it is sampled and excludes PII.
- Error reporting (T-034): one provider or a structured error log with alerting; payloads are
  scrubbed of PII and secrets.
- Dashboards: one per environment; staging is labelled so a test incident is never mistaken for
  production.

## 10. Backup, restore and disaster recovery
Targets: RPO ≤ 24 h, RTO ≤ 4 h (`docs/performance-profile.yaml`).
- **Database:** nightly `pg_dump` (custom format) plus WAL archiving if the provider supports
  PITR; encrypted at rest and in transit; stored off-host with a 30-day retention and monthly
  copy for 6 months.
- **Object storage:** bucket versioning in production; media is referenced by database rows and
  is not re-creatable, so it is backed up or replicated with the same retention.
- **Configuration/secrets:** documented in the secret store, not in the backup archive.
- **Restore drill (before GATE-1 and quarterly):** restore the latest dump into a clean
  database, run migrations, verify a sample company's counts (members, courses, enrollments,
  progress, audit) against the source report, start the app against it and open a learner page.
  The drill is recorded with date, backup id, duration and discrepancies.
- **Disaster recovery runbook:** declare incident → freeze writes → provision replacements →
  restore database and bucket → point DNS/ingress → verify health and a sample journey → announce.
  Data loss between the last backup and the incident is stated, never hidden.
- A backup older than 26 h is an alert; a failed restore is a release blocker.

## 11. Deployment and rollback runbook
1. Merge to `main` only with green gates; tag the release candidate.
2. Deploy the same image digest to staging; run migrations, smoke `/healthz`, `/readyz`, sign-in,
   one learner journey, one admin action.
3. Owner approves production. Take a pre-deploy backup; record the current digest.
4. Run backward-compatible migrations; deploy; watch 5xx/latency/queue for 30 min.
5. Rollback: redeploy the previous digest (code rollback is safe for one release because
   migrations are additive); if a migration must be reversed, use its documented reverse and
   restore from the pre-deploy backup when data was transformed.
6. Post-deploy: verify mail, reminders, backup schedule and alert delivery.

## 12. T-001 isolation checklist (historical evidence)
1. `git init -b main`, `origin` = `M_Academy`, documentation baseline committed and pushed.
2. `docker compose -p m-academy up -d --build --wait` succeeds.
3. `docker ps --filter name=m-academy-` lists exactly the seven containers; legacy containers
   remain `Up` and untouched.
4. `curl -sf http://localhost:8101/healthz` returns 200; legacy `8001/healthz` still answers.
5. `docker volume ls` shows only `m-academy_*` created by this task.
6. `docker network ls` shows `m-academy_default`; the legacy network is unchanged.
7. `migrate` runs against the new database, and `--profile setup run --rm createbuckets` creates the buckets.
8. A cookie set by this app is `m_academy_sessionid`; the legacy session is unaffected.
9. `.env` is untracked, `.env.example` has no secrets.
10. CI gates use this repository's secrets, not the legacy ones.

The bucket step remained open at T-001 and is re-verified in T-034.

## 13. Service targets and alert thresholds
Availability/recovery targets belong to `docs/performance-profile.yaml` (99.5% monthly, RPO ≤ 24 h,
RTO ≤ 4 h). Thresholds below are starting values, re-measured at the release load test.

| Signal | Warning | Critical | Action |
|---|---|---|---|
| `p95` non-media latency | > 300 ms for 10 min | > 600 ms for 5 min | Inspect slow queries; check N+1 |
| Heartbeat `p95` | > 150 ms for 10 min | > 400 ms for 5 min | Check Redis/DB saturation |
| 5xx rate | > 1% for 5 min | > 5% for 5 min | Roll back the last deploy |
| `default` queue oldest task | > 5 min | > 15 min | Scale worker, inspect stuck task |
| `media` queue depth | > 50 | > 200 | Scale media worker; check ffmpeg failures |
| Media failure ratio | > 20% in 1 h | > 40% in 1 h | Pause uploads, inspect `error_code` |
| Notification `failed` rows | > 20 in 1 h | > 100 in 1 h | Check SMTP/provider status; retry sweep |
| Reminder task not run at company hour | missed by 2 h | missed by 24 h | Check beat/worker; re-run for that company |
| DB connections | > 80% of the pool | > 95% | Check leaks; review `CONN_MAX_AGE` |
| Disk usage | > 80% | > 90% | Purge abandoned uploads; expand the volume |
| Last successful backup | > 26 h old | > 48 h old | Treat as an incident; run and verify a restore |
| Restore drill | overdue by 7 days | overdue by 30 days | Schedule the quarterly drill |
| Hub circuit open (only if enabled) | > 5 min | > 30 min | Notify the Hub owner; local writes continue |
| Audit mirror lag (only if enabled) | > 30 min | > 6 h | Check `academy.audit.mirror` and the Hub `activity` path |

Alerts route to the owner's channel in T-034; every alert carries the environment name. Two
consecutive failed probes or one critical threshold page the on-call owner.
