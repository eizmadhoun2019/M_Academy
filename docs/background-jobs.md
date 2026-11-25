# BACKGROUND JOBS — Celery Task Inventory

**Status:** Canonical. Fixes task names, queues, schedules, retries and idempotency.
**Last updated:** 2026-11-25
**Related:** `docs/configuration.md` §7 (broker/schedule), `docs/domain-model.md` §7.8
(reminder evaluation), `docs/notifications.md` (copy), `ARCHITECTURE.md` §4.

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
| `academy.progress.compact` | `default` | beat, daily 04:10 UTC | 900 s; no retry (next run covers it) | Merge of adjacent ranges with gap ≤ 0.5 s is convergent | Recalculates `watched_ranges`, `watched_seconds`, `frontier_seconds` for rows touched in the last 2 days |
| `academy.notifications.send` | `notifications` | On commit of a handler that creates a `pending` `NotificationLog` row; also the retry sweeper | soft 60 s / hard 90 s; 3 attempts, backoff 5 / 15 min | `UNIQUE(organization_id, dedupe_key, channel)`; `status='sent'` short-circuits | Renders the message from `docs/notifications.md` and delivers via the configured transport |
| `academy.notifications.sweep` | `notifications` | beat, every 15 min | soft 300 s / hard 330 s | Picks `pending`/`failed` rows with `attempt_count < 3`; the unique key prevents doubles | Re-enqueues `academy.notifications.send` |
| `academy.reminders.evaluate` | `default` | beat, hourly at minute 05; per company whose local hour equals `reminder_hour` | soft 1800 s / hard 1860 s; no retry (next tick re-evaluates) | `UNIQUE(enrollment_id, kind, recipient_membership_id)` on `ReminderLog`, checked in the same transaction that creates the notification | Emits `due_minus_3`, `due`, `due_plus_1` for active, incomplete, non-cancelled, unacknowledged enrollments with a due date |
| `academy.escalations.digest` | `notifications` | beat, hourly at minute 20, for the same company set at due+3 | soft 1800 s / hard 1860 s; 1 retry | `ReminderLog.kind='manager_escalation'` per `(enrollment, manager_membership)` and local due date | Sends one digest per manager covering their overdue learners (REQ-11) |
| `academy.accounts.purge_tokens` | `default` | beat, daily 04:40 UTC | 120 s; 1 retry | Deletes only expired/consumed tokens past their retention window | Keeps `AccountToken`/`EmailVerification` tables bounded |
| `academy.membership.reconcile` | `default` | beat, every `ACADEMY_MEMBERSHIP_RECONCILE_MINUTES` (60) | 600 s; 1 retry | Upserts only linked users; a directory failure leaves stored state unchanged | **Hub only** (registered only when `ACADEMY_HUB_ENABLED=true`): re-reads linked employees; a failed read is never a deactivation |
| `academy.audit.mirror` | `default` | beat, every 5 min | 120 s; 5 attempts, capped backoff 15 min | `AuditEvent.event_id` is the outbound idempotency key | **Hub only**: pushes unmirrored events to the Hub `activity` path; stops when the circuit is open |

With the default `ACADEMY_HUB_ENABLED=false`, the last two tasks are **not registered and not
scheduled** (T-033 asserts the beat dictionary and task registry). No job performs a Hub lookup
in standalone mode.

## 2. Per-company reminder scheduling
`ACADEMY_BUSINESS_TZ` no longer drives reminders. Each `Organization` has `timezone` and
`reminder_hour` (default 08:00 local; D-038). The hourly tick selects companies where
`localtime(now, company.timezone).hour == company.reminder_hour`, then evaluates that company's
enrollments in its own scope. Consequences:

- Two companies in different zones get their reminders at their own 08:00, not one global hour.
- A DST transition can make an hour repeat or vanish. Repeating is harmless because the
  `ReminderLog` unique key suppresses a second send; a vanished hour skips that company's
  reminder for the day (no tick matches the configured hour); the next day's tick re-evaluates
  the same conditions and the unique key still prevents a duplicate.
- The task is safe to run twice: it sends nothing already recorded for that enrollment/kind.
- A paused company is skipped; a suspended membership is skipped; a cancelled enrollment is
  skipped.

## 3. Explicitly not background jobs

| Work | Why synchronous |
|---|---|
| Heartbeat / lesson completion | Must be server-authoritative and answered inside the request (`docs/domain-model.md` §7) |
| CSV export | Streamed inside the request with a bounded, indexed query; no partial-file cleanup |
| Privacy export/anonymize | Request-scoped, audited, returns a JSON bundle (REQ-19) |
| Publish validation | Runs in the publish transaction so `422 publish_invalid` is exact |
| Account email verification/reset | Token creation is transactional; delivery is queued like other mail |
| Hub webhook handling | The route acknowledges after the durable local write; no queue hop (only when enabled) |

## 4. Failure behaviour
- A `media` task that exhausts retries sets `status='failed'` with a stable `error_code`
  (`probe_failed`, `transcode_failed`, `duration_exceeded`, `storage_unavailable`) and is
  reported by the media alert; `POST …/retry/` resets the counter up to
  `ACADEMY_TRANSCODE_ATTEMPTS`.
- An email failure sets `NotificationLog.status='failed'` with `error_code` and increments
  `attempt_count`; the UI never shows a failed message as sent.
- Reminder evaluation that crashes mid-run is safe: the unique constraint means the next tick
  sends only what is missing.
- A missed reminder tick self-heals: the next tick for that company's configured hour (or the
  next day) evaluates the same conditions; the copy is rendered at send time.
- `academy.audit.mirror` never blocks a request and never loses the local event; mirror lag is
  measurable (`docs/operations/environments.md` §8) and exists only in Hub mode.

## 5. Beat schedule (single source)

| Time | Task |
|---|---|
| every 5 min | `academy.audit.mirror` (Hub only) |
| every 15 min | `academy.notifications.sweep` |
| every 60 min | `academy.membership.reconcile` (Hub only) |
| hourly at :05 | `academy.reminders.evaluate` |
| hourly at :20 | `academy.escalations.digest` |
| 03:10 daily UTC | `academy.media.purge_abandoned` |
| 04:10 daily UTC | `academy.progress.compact` |
| 04:40 daily UTC | `academy.accounts.purge_tokens` |

The schedule is declared in code (`CELERY_BEAT_SCHEDULE`), never edited in the admin, so the
deployed schedule matches this table at review time. UTC entries are infrastructure housekeeping
and intentionally zone-independent; learner-facing reminders use each company's zone. Every entry
names a task that exists in the registry for the active mode.

## 6. Test obligations
- Eager mode in tests; each task called twice leaves one effect (double-delivery test).
- Reminder evaluation at frozen time produces exactly the expected `ReminderLog` rows for a
  matrix of due dates (−5, −3, −1, 0, +1, +3, +5 days), skips acknowledged ones, and across two
  companies/time zones fires each at its own local hour (including a DST boundary).
- `media.process` failure paths set `failed` + `error_code` and never leave `ready` without a
  playlist.
- `accounts.purge_tokens` removes only expired/consumed rows past retention.
- Hub disabled: `membership.reconcile`/`audit.mirror` absent from the registry and beat, and no
  outbound call is attempted. Hub enabled: existing contract behaviour still holds.
