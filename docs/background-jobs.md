# BACKGROUND JOBS — Celery Task Inventory

**Status:** Canonical. Fixes task names, queues, schedules, retries and idempotency so that
T-018, T-021 and T-024 implement the same catalogue.
**Last updated:** 2026-11-22
**Related:** `docs/configuration.md` §2 (broker), `docs/domain-model.md` §7.8 (reminder
evaluation), `docs/notifications.md` (copy), `ARCHITECTURE.md` §4 (components).

Queues: `default`, `media`, `notifications` (fixed in `docs/operations/environments.md` §4).
Workers: `default` concurrency 4, `media` 2, `notifications` 2 — development uses 1 each.
Broker and result backend are this project's own Redis (DB 1 and 2).

Global settings: `task_acks_late=true`, `worker_prefetch_multiplier=1`,
`task_reject_on_worker_lost=true`, `broker_connection_retry_on_startup=true`,
`result_expires=86400`, `timezone=UTC`. Every task is **idempotent**; re-running it must not
duplicate a user-visible effect. Exactly one `beat` process runs at a time.

---

## 1. Catalogue

| Task | Queue | Trigger | Timeout / retries | Idempotency key | Effect |
|---|---|---|---|---|---|
| `academy.media.process` | `media` | `POST /manage/media/{id}/complete/` after `stat` verification | soft 3300 s, hard 3600 s; 2 retries, backoff 60 s / 300 s | `MediaAsset.status` transition under `SELECT … FOR UPDATE`; a `ready` asset is never reprocessed | `ffprobe` → duration/limit check → ffmpeg → HLS renditions + poster → `status='ready'`, `ready_at` |
| `academy.media.purge_abandoned` | `default` | beat, daily 03:10 UTC | 300 s; 1 retry | Deletes only `status='awaiting_upload'` older than `ACADEMY_UPLOAD_ABANDON_HOURS` | Frees orphan storage objects and rows |
| `academy.progress.compact` | `default` | beat, daily 04:10 UTC | 900 s; no retry (next run covers it) | Re-normalization is convergent: merging adjacent ranges with gap ≤ 0.5 s always yields the same result | Recalculates `watched_ranges`, `watched_seconds`, `frontier_seconds` for rows touched in the last 2 days |
| `academy.notifications.send` | `notifications` | On commit of a domain handler that creates a `pending` `NotificationLog` row; also the retry sweeper | soft 60 s / hard 90 s; 3 attempts, backoff 5 / 15 min | `UNIQUE(organization_id, dedupe_key, channel)`; `status='sent'` short-circuits | Renders the message from `docs/notifications.md` and delivers by channel |
| `academy.notifications.sweep` | `notifications` | beat, every 15 min | soft 300 s / hard 330 s | Picks `pending`/`failed` rows with `attempt_count < 3`; the unique key prevents doubles | Re-enqueues `academy.notifications.send` |
| `academy.reminders.evaluate` | `default` | beat, daily at 08:00 `ACADEMY_BUSINESS_TZ` (D-002) | soft 1800 s / hard 1860 s; no retry (idempotent, next run re-evaluates) | `UNIQUE(enrollment_id, kind, recipient_ref)` on `ReminderLog`, checked in the same transaction that creates the notification | Emits `due_minus_3`, `due`, `due_plus_1` for active, incomplete, non-cancelled enrollments with a due date that is not yet acknowledged |
| `academy.escalations.digest` | `notifications` | beat, daily at 08:00 `ACADEMY_BUSINESS_TZ`, for enrollments at due+3; with no arguments it sends every batch still owed a digest | soft 1800 s / hard 1860 s; 1 retry | `ReminderLog.kind='manager_escalation'` per `(enrollment, manager)` | Sends one digest per manager covering their overdue learners (REQ-11) |
| `academy.membership.reconcile` | `default` | beat, every `ACADEMY_MEMBERSHIP_RECONCILE_MINUTES` (60) | 600 s; 1 retry | Upserts only linked users; a directory failure leaves stored state unchanged | Re-reads linked employees from the Hub directory (D-029); a failed read is never treated as a deactivation |
| `academy.audit.mirror` | `default` | beat, every 5 min | 120 s; 5 attempts, capped backoff 15 min | `AuditEvent.event_id` is the outbound idempotency key | Pushes unmirrored events to the Hub `activity` path through `HubHttp`; stops silently when the circuit is open |

## 2. Explicitly not background jobs

| Work | Why synchronous |
|---|---|
| Heartbeat / lesson completion | Must be server-authoritative and answered inside the request (§7 of the domain model) |
| CSV export | Streamed inside the request with a bounded, indexed query; no partial-file cleanup |
| Privacy export/anonymize | Request-scoped, audited, returns a JSON bundle (REQ-19) |
| Publish validation | Runs in the publish transaction so `422 publish_invalid` is exact |
| Hub webhook handling | The route acknowledges after the durable local write; no queue hop |

## 3. Failure behaviour

- A `media` task that exhausts retries sets `status='failed'` with a stable `error_code`
  (`probe_failed`, `transcode_failed`, `duration_exceeded`, `storage_unavailable`) and is
  reported by the media alert; `POST …/retry/` resets the counter up to
  `ACADEMY_TRANSCODE_ATTEMPTS`.
- An email failure sets `NotificationLog.status='failed'` with `error_code` and increments
  `attempt_count`; the UI never shows a failed message as sent.
- Reminder evaluation that crashes mid-run is safe: the unique constraint means the next run
  sends only what is missing.
- Deadline-sensitive tasks are **not** retried indefinitely: reminders and digests are
  re-evaluated daily, so a missed run self-heals the next morning rather than sending a
  stale reminder later the same day.
- `academy.audit.mirror` never blocks a request and never loses the local event; mirror
  lag is measurable (see alerts in `docs/operations/environments.md` §8).

## 4. Beat schedule (single source)

| Time | Task |
|---|---|
| every 15 min | `academy.notifications.sweep` |
| every 5 min | `academy.audit.mirror` |
| every 60 min | `academy.membership.reconcile` |
| 03:10 daily UTC | `academy.media.purge_abandoned` |
| 04:10 daily UTC | `academy.progress.compact` |
| 08:00 daily business TZ | `academy.reminders.evaluate`, `academy.escalations.digest` |

Schedule is declared in code (`CELERY_BEAT_SCHEDULE`), never edited in the admin, so the
deployed schedule matches this table at review time. Celery itself beats in UTC, so the one
business-time entry converts 08:00 to a UTC hour when the process starts; the default zone is
UTC (D-002), and a zone with DST drifts by an hour until the next deploy.

The other rows of the table (`academy.media.purge_abandoned`, `academy.progress.compact`,
`academy.membership.reconcile`, `academy.audit.mirror`) join the same dictionary with the tasks
that implement them, so no entry names a task that does not exist yet.

## 5. Test obligations

- Eager mode in tests; each task called twice leaves one effect (double-delivery test).
- Reminder evaluation at frozen time produces exactly the expected `ReminderLog` rows for a
  matrix of due dates (−5, −3, −1, 0, +1, +3, +5 days) and skips acknowledged ones.
- `media.process` failure paths set `failed` + `error_code` and never leave `ready` without a
  playlist.
- `audit.mirror` with the Hub circuit open retries later and mirror lag stays observable.
- `membership.reconcile` with a failing directory changes no link and cancels no enrollment.
