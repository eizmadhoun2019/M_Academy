# ENVIRONMENTS — Repository, Stack Names and Isolation

**Status:** Canonical. `ARCHITECTURE.md` §8 and `README.md` defer to this file.
**Last updated:** 2026-11-22
**Owner decision:** D-023 Confirmed (2026-11-22) — the repository stays public; the baseline is published.

This file makes the isolation rule enforceable. The new project runs as a **separate stack**
next to the legacy `Masheed-Academy` deployment on the same host, sharing nothing: not a
network, volume, database, cache, bucket, credential or port.

---

## 1. Repository

| Item | Value |
|---|---|
| Repository | `https://github.com/eizmadhoun2019/M_Academy` |
| Default branch | `main` |
| Task branches | `task/<T-NNN>-<slug>` (RULES) |
| Local workspace | this directory — its own git repository, `origin` = `M_Academy` |
| Legacy repository | `Masheed-Academy` — reference only, never a remote, never cloned into this tree |

Rules:
- This repository has its **own history**. No legacy commit, tag, branch, image tag or
  credential is imported. The first commit is the documentation baseline.
- The legacy repository and its deployment stay alive and unmodified. Reading it for context
  is allowed; copying from it is not — anything reused is re-derived from these documents
  and re-implemented here.
- Publication is authorized: the repository is public (D-023 Confirmed, 2026-11-22).
  Everything pushed is world-readable, so secrets never enter a tracked file.

## 2. Stack identity

| Item | Value | Must not collide with |
|---|---|---|
| Compose project | `m-academy` | `masheed-academy` (legacy, running) |
| Compose files | `docker-compose.yml` (+ `docker-compose.override.yml` if needed) | — |
| Network | `m-academy_default` (compose-managed) | `masheed-academy_default` |
| Container names | `m-academy-{web,db,redis,minio,worker,beat,mailhog}-1` | `masheed-academy-*` |
| Local image tags | `m-academy-web:dev`, `m-academy-worker:dev` | legacy image names |
| Env file | `.env` (untracked) + `.env.example` (tracked, no secrets) | legacy `.env` |

Always pass the project name explicitly so a Mistyped `down` can never reach another stack:

```bash
docker compose -p m-academy up -d --build --wait
docker compose -p m-academy ps
```

## 3. Host ports (verified free on 2026-11-22)

The legacy stack already holds `8001` (web), `9000`/`9001` (MinIO) and `8026` (MailHog) on
127.0.0.1, and other local projects hold `8000`, `8025`, `15432`, `16379`, `16380`. The
values below were checked as free at the time of writing and are reserved for this project.

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
- If any value is taken when T-001 runs, pick the next free value here first, then implement.

## 4. Data isolation

| Concern | This project | Never |
|---|---|---|
| PostgreSQL cluster | container `m-academy-db-1`, volume `m-academy_pgdata`, database `academy`, role `academy` | connect to the legacy database or reuse its volume |
| Redis | container `m-academy-redis-1`, volume `m-academy_redisdata` | reuse the legacy Redis instance |
| Redis DB indexes | `0` cache (key prefix `macademy:`), `1` Celery broker, `2` results | assume another project's DB index |
| Object storage | container `m-academy-minio-1`, volume `m-academy_miniodata`, buckets `academy-media-dev`, `academy-media-test` | reuse a legacy bucket |
| Media working directory | volume `m-academy_media` | share a host folder with the legacy worker |
| Celery queues | `default`, `media`, `notifications` — isolation comes from the separate broker, names need no suffix | point a worker at another project's broker |
| Secrets | freshly generated at T-001: `DJANGO_SECRET_KEY`, DB password, MinIO keys, Hub identity/webhook key rings | copy any legacy key |
| Email | MailHog in dev; Hub mail API in production | use the legacy MailHog container |

## 5. Name-scoped browser state

Browsers scope cookies by **host, not port**, so `localhost:8001` (legacy) and
`localhost:8101` (this project) share a cookie jar.

| Item | Value |
|---|---|
| Django session cookie | `m_academy_sessionid` |
| CSRF cookie | `academy_csrftoken`, `Path=/academy/` in the proxy deployment |
| Storage prefix inside a bucket | `org/<organization_id>/...` |

Never use a bare `sessionid` or `csrftoken` name: it would collide with the legacy app and
with any other local Django project.

## 6. Coexistence and safety rules

**Allowed:** `docker compose -p m-academy …` on this project only; reading
`docker ps`/`docker logs` for diagnosis; stopping only `m-academy-*` containers that this
project started.

**Prohibited** (also in RULES → AI agent permissions):
- `docker system prune`, `docker volume prune`, `docker network prune`, `docker rm -f`,
  `docker image prune -a` — each can destroy another project's data or images.
- `docker compose down` without `-p m-academy`, or run in another project's directory.
- Stopping, restarting, recreating or editing `masheed-academy-*` containers, its volumes,
  network or compose file.
- Dropping, restoring or migrating any database other than `m-academy-db-1`.

Resource note: both stacks run at once, so the media worker concurrency is `1` in
development and the beat schedule is disabled when a second `beat` would duplicate
reminders (only one `m-academy-beat-1` at a time).

## 7. T-001 isolation checklist (part of its acceptance)

1. `git init -b main` here, add `origin` = `M_Academy`, commit the documentation baseline.
   Push authorized (D-023 Confirmed) and executed: `origin/main` carries the rebased history.
2. `docker compose -p m-academy up -d --build --wait` succeeds.
3. `docker ps --filter name=m-academy-` lists exactly the seven containers; `docker ps` shows
   the legacy `masheed-academy-*` containers still `Up` and untouched.
4. `curl -sf http://localhost:8101/healthz` returns 200; `http://localhost:8001/healthz`
   (legacy) still answers.
5. `docker volume ls` shows only `m-academy_*` created by this task.
6. `docker network ls` shows `m-academy_default`; the legacy network is unchanged.
7. `migrate` and `ensure_development_storage` run against the new database and buckets;
   `academy-media-dev` exists and is empty.
8. A cookie set by this app is `m_academy_sessionid`; the legacy session is unaffected.
9. `.env` is untracked (`git check-ignore .env`), `.env.example` has no secrets.
10. CI gates G1–G9 configured for this repository with its own secrets, not the legacy ones.

## 8. Service targets and alert thresholds (T-024)

Availability and recovery targets belong to `docs/performance-profile.yaml`
(99.5% monthly, RPO ≤ 24 h, RTO ≤ 4 h). These are the thresholds that turn them into alerts;
they are starting values, re-measured at the release load test.

| Signal | Warning | Critical | Action |
|---|---|---|---|
| `p95` non-media latency | > 300 ms for 10 min | > 600 ms for 5 min | Inspect slow queries; check N+1 |
| Heartbeat `p95` | > 150 ms for 10 min | > 400 ms for 5 min | Check Redis/DB saturation |
| 5xx rate | > 1% for 5 min | > 5% for 5 min | Roll back the last deploy |
| `default` queue oldest task | > 5 min | > 15 min | Scale worker, inspect stuck task |
| `media` queue depth | > 50 | > 200 | Scale media worker; check ffmpeg failures |
| Media failure ratio | > 20% in 1 h | > 40% in 1 h | Pause uploads, inspect `error_code` |
| Notification `failed` rows | > 20 in 1 h | > 100 in 1 h | Check Hub mail API and circuit state |
| Hub circuit open | > 5 min | > 30 min | Notify the Hub owner; local writes continue |
| Audit mirror lag | > 30 min | > 6 h | Check `academy.audit.mirror` and Hub `activity` path |
| DB connections | > 80% of the pool | > 95% | Check leaks; raise `CONN_MAX_AGE` review |
| Disk usage | > 80% | > 90% | Purge abandoned uploads; expand the volume |
| Last successful backup | > 26 h old | > 48 h old | Treat as an incident; run and verify a restore |
| Restore drill | overdue by 7 days | overdue by 30 days | Schedule the quarterly drill |

Alerts route to the owner's channel in T-024; every alert carries the environment name
(`development`/`production`) so a test incident is never mistaken for a real one.
