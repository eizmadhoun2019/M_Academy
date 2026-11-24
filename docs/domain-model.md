# DOMAIN MODEL — Entities, Constraints, State Machines and the Progress Algorithm

**Status:** Canonical schema specification. `ARCHITECTURE.md` §5 summarizes; this file decides.
**Last updated:** 2026-11-22
**Implements:** REQ-03, REQ-06, REQ-07, REQ-08, REQ-09, REQ-10, REQ-11, REQ-13, REQ-19
**Depends on:** `docs/decisions.md` (D-013…D-017, D-003), `docs/api.md`, `docs/hub-contract.md`

Any change here follows `docs/skills/model-change.md`. PostgreSQL is the only supported
database (ADR 008); SQLite is never used, not even in tests.

---

## 1. Conventions

### 1.1 Base model
Every concrete model subclasses `academy.models.TenantModel` (meta-test enforced):

| Column | Type | Rules |
|---|---|---|
| `id` | `uuid` (v4) | Primary key, generated in Python |
| `organization_id` | `uuid` | NOT NULL. Never a FK — the organization lives in Hub |
| `created_at` | `timestamptz` | NOT NULL, set once, `timezone.now()` only |
| `updated_at` | `timestamptz` | NOT NULL, auto |

- Managers: `objects` (unrestricted, migrations and tests only) and
  `TenantModel.objects.for_org(organization_id)` — every runtime read goes through `for_org`.
- Every index whose first column is not a unique key **must** start with `organization_id`.
- No FK points to a user. Users appear only as opaque `*_ref` strings (`VARCHAR(64)`,
  `^[A-Za-z0-9._:-]{1,64}$`). Department refs use the same pattern. Names and emails are
  never stored.
- Enumerations are Django `TextChoices` **plus** a `CheckConstraint` (no DB enum types, so
  adding a value is a plain code change).

### 1.2 Reference table
| Column | Meaning |
|---|---|
| `*_ref` | Opaque Hub reference (user or department) |
| `actor_ref` | Who performed an audited action; `"system"` for scheduled work |
| `dedupe_key` | Idempotency key of an outbound side effect |

---

## 2. Entities

Order is the migration order. “Derived” means it is computed and never stored.

### 2.1 `Course`
Container for versions.

| Field | Type | Null | Default | Constraints / notes |
|---|---|---|---|---|
| `title` | varchar(200) | no | — | Non-blank |
| `description` | text | yes | `''` | |
| `owner_department_ref` | varchar(64) | yes | `NULL` | D-013. `NULL` = general course (admin-only edit) |
| `status` | varchar(16) | no | `draft` | `draft \| published \| archived` |
| `created_by_ref` | varchar(64) | no | — | |

Constraints: `CHECK (status IN ('draft','published','archived'))`,
`CHECK (length(btrim(title)) > 0)`.
Indexes: `(organization_id, status)`, `(organization_id, owner_department_ref)`.
The published version is **derived** from `CourseVersion` (§2.2); there is no
`Course.published_version` column (single source of truth).

### 2.2 `CourseVersion`
An immutable snapshot once published.

| Field | Type | Null | Default | Constraints / notes |
|---|---|---|---|---|
| `course_id` | uuid FK → Course | no | — | `ON DELETE RESTRICT` |
| `version_number` | integer | no | — | ≥ 1, assigned by the clone service |
| `status` | varchar(16) | no | `draft` | `draft \| published \| archived` |
| `acknowledgment_required` | boolean | no | `false` | Learner must tick acknowledgment |
| `cover_media_id` | uuid FK → MediaAsset | yes | `NULL` | D-014, must belong to the same organization |
| `published_at` | timestamptz | yes | `NULL` | NOT NULL iff `status = 'published'` |
| `published_by_ref` | varchar(64) | yes | `NULL` | Same rule |
| `created_by_ref` | varchar(64) | no | — | |

Constraints:
- `UNIQUE (course_id, version_number)`
- `UNIQUE (course_id) WHERE status = 'published'` — at most one published version per course.
- `CHECK (status <> 'published' OR (published_at IS NOT NULL AND published_by_ref IS NOT NULL))`
- Immutability trigger `courseversion_immutable`: `UPDATE` of any column except
  `status`/`published_at`/`published_by_ref` is rejected when the row is `published`; the
  only allowed status transition is `published → archived`.
Indexes: `(organization_id, course_id)`, partial `(organization_id) WHERE status = 'published'`.

### 2.3 `Section`

| Field | Type | Null | Default | Constraints |
|---|---|---|---|---|
| `version_id` | uuid FK → CourseVersion | no | — | `ON DELETE CASCADE` |
| `title` | varchar(200) | no | — | Non-blank |
| `position` | integer | no | — | ≥ 1 |

Constraints: `UNIQUE (version_id, position) DEFERRABLE INITIALLY DEFERRED`,
`CHECK (position >= 1)`. Child writes are rejected when the version is `published`
(trigger `version_content_frozen`).

### 2.4 `Lesson`

| Field | Type | Null | Default | Constraints / notes |
|---|---|---|---|---|
| `section_id` | uuid FK → Section | no | — | `ON DELETE CASCADE` |
| `title` | varchar(200) | no | — | Non-blank |
| `summary` | varchar(300) | yes | `NULL` | D-016 |
| `body` | text | yes | `''` | Text/PDF lesson body |
| `position` | integer | no | — | ≥ 1 |
| `content_type` | varchar(16) | no | `video` | `video \| text \| pdf` |
| `media_asset_id` | uuid FK → MediaAsset | yes | `NULL` | Required for `video` at publish time, not at draft |
| `required` | boolean | no | `true` | Non-required lessons are skipped by the lock chain |
| `required_watch_percent` | smallint | no | `90` | `CHECK BETWEEN 50 AND 100` |

Constraints: `UNIQUE (section_id, position) DEFERRABLE INITIALLY DEFERRED`,
`CHECK (content_type IN ('video','text','pdf'))`, `CHECK (position >= 1)`,
`CHECK (content_type <> 'pdf' OR body IS NOT NULL)` (service-validated at publish for video
media readiness — see §4 invariants).

### 2.5 `MediaAsset`

| Field | Type | Null | Default | Constraints / notes |
|---|---|---|---|---|
| `kind` | varchar(16) | no | `video` | `video \| image \| document` (D-014) |
| `status` | varchar(20) | no | `awaiting_upload` | See state machine §5 |
| `storage_key` | varchar(512) | yes | `NULL` | Prefix + UUID + extension; never a URL |
| `original_filename` | varchar(255) | yes | `NULL` | Display only, sanitized |
| `content_type` | varchar(100) | yes | `NULL` | Trusted only after `stat` verification against an allowlist |
| `size_bytes` | bigint | yes | `NULL` | `CHECK (size_bytes IS NULL OR size_bytes >= 0)` |
| `checksum_sha256` | char(64) | yes | `NULL` | Lowercase hex |
| `duration_seconds` | numeric(10,3) | yes | `NULL` | From ffprobe; videos only |
| `renditions` | jsonb | no | `'{}'` | `{"360p": {...}, "720p": {...}}` written by the pipeline |
| `error_code` | varchar(40) | yes | `NULL` | e.g. `probe_failed`, `transcode_failed` |
| `attempt_count` | smallint | no | `0` | |
| `ready_at` | timestamptz | yes | `NULL` | |
| `created_by_ref` | varchar(64) | no | — | |

Constraints:
- `CHECK (kind IN ('video','image','document'))`
- `CHECK (status <> 'ready' OR storage_key IS NOT NULL)`
- `CHECK (kind <> 'video' OR status <> 'ready' OR duration_seconds > 0)`
- `CHECK (status <> 'failed' OR error_code IS NOT NULL)`
Indexes: `(organization_id, status)`, `(organization_id, created_at)` for stale purging.

### 2.6 `Assignment`
One target, one course.

| Field | Type | Null | Default | Constraints / notes |
|---|---|---|---|---|
| `course_id` | uuid FK → Course | no | — | `ON DELETE RESTRICT` |
| `target_type` | varchar(16) | no | — | `user \| department \| role \| organization` (D-015) |
| `target_ref` | varchar(64) | yes | `NULL` | `NULL` iff `target_type = 'organization'` |
| `due_at` | timestamptz | yes | `NULL` | Stored UTC |
| `mandatory` | boolean | no | `true` | |
| `assigned_by_ref` | varchar(64) | no | — | |
| `note` | varchar(500) | yes | `NULL` | |
| `cancelled_at` | timestamptz | yes | `NULL` | Soft cancel; never delete |

Constraints:
- `CHECK (target_type IN ('user','department','role','organization'))`
- `CHECK ((target_type = 'organization' AND target_ref IS NULL) OR (target_type <> 'organization' AND target_ref IS NOT NULL))`
- `UNIQUE (organization_id, course_id, target_type, target_ref) WHERE cancelled_at IS NULL`
  — note: `NULL` in a unique index does not collide, so use a
  `COALESCE(target_ref, '')` expression index for the `organization` case.
- `CHECK (cancelled_at IS NULL OR cancelled_at >= created_at)`

### 2.7 `Enrollment`
Pins a learner to one published version.

| Field | Type | Null | Default | Constraints / notes |
|---|---|---|---|---|
| `assignment_id` | uuid FK → Assignment | yes | `NULL` | `NULL` = direct/self enrollment |
| `course_id` | uuid FK → Course | no | — | Denormalized for reporting |
| `course_version_id` | uuid FK → CourseVersion | no | — | Pinned; never follows later publishes |
| `user_ref` | varchar(64) | no | — | |
| `due_at` | timestamptz | yes | `NULL` | Copied from the assignment at creation |
| `mandatory` | boolean | no | `true` | Copied at creation |
| `status` | varchar(16) | no | `active` | `active \| completed \| cancelled` |
| `acknowledged_at` | timestamptz | yes | `NULL` | |
| `completed_at` | timestamptz | yes | `NULL` | |
| `cancelled_at` | timestamptz | yes | `NULL` | |
| `cancel_reason` | varchar(40) | yes | `NULL` | `unassigned \| deactivated \| removed_from_target` |

Constraints:
- `UNIQUE (organization_id, user_ref, course_id) WHERE status = 'active'`
- `CHECK (status <> 'completed' OR completed_at IS NOT NULL)`
- `CHECK (status <> 'cancelled' OR cancelled_at IS NOT NULL)`
- `CHECK (course_version_id IS NOT NULL)` — the service refuses to enroll onto a draft.
- Re-enrollment inserts a **new** row: the partial unique index covers `active` rows only, so a
  cancelled enrollment never blocks a new one, and reactivation never revives a cancelled row
  (D-028).
Indexes: `(organization_id, user_ref, status)`, `(organization_id, course_id, status)`,
`(organization_id, due_at) WHERE status = 'active' AND due_at IS NOT NULL`.

### 2.8 `LessonProgress`

| Field | Type | Null | Default | Constraints / notes |
|---|---|---|---|---|
| `enrollment_id` | uuid FK → Enrollment | no | — | `ON DELETE CASCADE` |
| `lesson_id` | uuid FK → Lesson | no | — | |
| `watched_ranges` | jsonb | no | `'[]'` | Ascending, disjoint `[[start, end], …]` seconds, 0.1 s precision |
| `watched_seconds` | numeric(10,1) | no | `0` | Derived cache of the ranges sum |
| `position_seconds` | numeric(10,1) | no | `0` | Last accepted position (server frontier source) |
| `frontier_seconds` | numeric(10,1) | no | `0` | Longest contiguous run from 0 |
| `last_heartbeat_at` | timestamptz | yes | `NULL` | Server clock only |
| `skip_attempts` | integer | no | `0` | Rejected forward jumps (abuse metric) |
| `completed_at` | timestamptz | yes | `NULL` | Set by the completion service, not by heartbeat |

Constraints: `UNIQUE (enrollment_id, lesson_id)`,
`CHECK (watched_seconds >= 0)`, `CHECK (position_seconds >= 0)`,
`CHECK (frontier_seconds >= 0)`, `CHECK (frontier_seconds <= position_seconds)`.
The ranges invariant (ascending, disjoint, non-negative) is enforced in the service, not by
a check constraint; the compaction task re-normalizes.

### 2.9 `CompletionRecord`
Immutable proof of completion.

| Field | Type | Null | Default | Constraints |
|---|---|---|---|---|
| `enrollment_id` | uuid FK → Enrollment | no | — | |
| `course_id`, `course_version_id` | uuid | no | — | Snapshot for reporting |
| `user_ref` | varchar(64) | no | — | Snapshot |
| `completed_at` | timestamptz | no | — | |
| `method` | varchar(16) | no | `lessons` | `lessons \| admin_override` |
| `actor_ref` | varchar(64) | no | — | Learner ref, or the admin for overrides |

Constraints: `UNIQUE (enrollment_id)`. Trigger rejects `UPDATE` and `DELETE`.

### 2.10 Quiz tables (Phase 1: schema only)
`Quiz` (`version_id`, `lesson_id` nullable, `title`, `pass_percent` 0–100, `max_attempts`),
`QuizQuestion` (`quiz_id`, `position`, `prompt`, `kind` = `single|multiple`),
`QuizChoice` (`question_id`, `position`, `label`, `is_correct`),
`QuizAttempt` (`quiz_id`, `enrollment_id`, `started_at`, `submitted_at`, `score_percent`,
`passed`), `QuizAttemptAnswer` (`attempt_id`, `question_id`, `choice_ids` jsonb, `correct`).
Each with the standard tenant columns and `UNIQUE(quiz_id, enrollment_id, attempt_number)`.
**No Phase 1 endpoint writes these tables**; they exist so Phase 2 needs no destructive
migration.

### 2.11 `ReminderLog`
| Field | Type | Null | Default | Constraints |
|---|---|---|---|---|
| `enrollment_id` | uuid FK → Enrollment | no | — | |
| `kind` | varchar(24) | no | — | `due_minus_3 \| due \| due_plus_1 \| manager_escalation` |
| `recipient_ref` | varchar(64) | no | — | Learner, or the manager for escalation |
| `sent_at` | timestamptz | no | — | Server clock |

`UNIQUE (enrollment_id, kind, recipient_ref)` — the idempotency mechanism.

### 2.12 `NotificationLog`
| Field | Type | Null | Default | Constraints |
|---|---|---|---|---|
| `kind` | varchar(32) | no | — | `course_assigned \| course_completed \| learner_completed \| manager_escalation` |
| `dedupe_key` | varchar(128) | no | — | e.g. `completed:e-79`, `assigned:a-12:u-42` |
| `recipient_ref` | varchar(64) | no | — | |
| `channel` | varchar(16) | no | `email` | `email \| in_app` |
| `status` | varchar(16) | no | `pending` | `pending \| sent \| failed \| skipped` |
| `attempt_count` | smallint | no | `0` | |
| `error_code` | varchar(40) | yes | `NULL` | |
| `sent_at` | timestamptz | yes | `NULL` | |

`UNIQUE (organization_id, dedupe_key, channel)`, `CHECK (status <> 'sent' OR sent_at IS NOT NULL)`.

### 2.13 `AuditEvent` (append-only)
| Field | Type | Null | Default | Constraints |
|---|---|---|---|---|
| `event_id` | uuid | no | — | Idempotency for the Hub mirror |
| `actor_ref` | varchar(64) | no | — | `"system"` allowed |
| `action` | varchar(64) | no | — | Dotted, e.g. `course.published`, `grant.denied` |
| `object_type` | varchar(32) | no | — | |
| `object_id` | varchar(64) | no | — | UUID or opaque ref |
| `metadata` | jsonb | no | `'{}'` | IDs only — never names, emails, IPs or free text |
| `occurred_at` | timestamptz | no | — | Same instant as the caller's transaction |

`UNIQUE (organization_id, event_id)`; index `(organization_id, object_type, object_id)`,
`(organization_id, occurred_at)`; `BEFORE UPDATE OR DELETE` trigger raises (`academy_guard_audit_event`, migration `0004`).
Rows are written only through `academy.audit.record`, which validates the action name and
the ids-only metadata and returns the existing row for a repeated `event_id`.

### 2.14 `PermissionGrant`
| Field | Type | Null | Default | Constraints |
|---|---|---|---|---|
| `user_ref` | varchar(64) | no | — | |
| `capability` | varchar(24) | no | — | `learn \| manage_content \| assign \| view_reports \| admin` |
| `scope_type` | varchar(16) | no | — | `organization \| department` |
| `scope_ref` | varchar(64) | yes | `NULL` | Department ref; `NULL` iff organization scope |
| `granted_by_ref` | varchar(64) | no | — | |
| `expires_at` | timestamptz | yes | `NULL` | |
| `revoked_at` | timestamptz | yes | `NULL` | |
| `revoked_by_ref` | varchar(64) | yes | `NULL` | |

Constraints:
- `CHECK ((scope_type = 'organization' AND scope_ref IS NULL) OR (scope_type = 'department' AND scope_ref IS NOT NULL))`
- `UNIQUE (organization_id, user_ref, capability, scope_type, COALESCE(scope_ref, '')) WHERE revoked_at IS NULL`
- `CHECK (revoked_at IS NULL OR revoked_by_ref IS NOT NULL)`

### 2.15 `AccessSuspension` (Academy-local)

D-028: a local administrative suspension makes stored grants ineffective without deleting
them, and never changes Hub membership.

| Field | Type | Null | Default | Constraints |
|---|---|---|---|---|
| `user_ref` | varchar(64) | no | — | |
| `reason` | varchar(500) | no | — | Non-blank |
| `suspended_at` | timestamptz | no | — | Set by the service, `timezone.now()` |
| `suspended_by_ref` | varchar(64) | no | — | Effective `academy.admin` |
| `lifted_at` | timestamptz | yes | `NULL` | Manual lift only |
| `lifted_by_ref` | varchar(64) | yes | `NULL` | Required iff `lifted_at` is set |

Constraints: `UNIQUE (organization_id, user_ref) WHERE lifted_at IS NULL`,
`CHECK (lifted_at IS NULL OR lifted_by_ref IS NOT NULL)`, `CHECK (length(btrim(reason)) > 0)`.
Enforcement is in the authorization layer: an active row yields no effective capability, the
next request is denied with `403 access_suspended`, and the learner sees screen X2. No local
membership row and no session store are added.

### 2.16 Deliberately absent
| Not stored | Why |
|---|---|
| Per-heartbeat rows | Volume (14 req/s → 1.2 M rows/day) and privacy; merged ranges suffice (ADR-013) |
| IP address, user agent, device id | Privacy minimization; not needed for the requirements |
| Local membership projection | Hub is the directory; membership is read on demand and cached 60 s (ADR-012) |
| User names and emails | Never stored; fetched per request when a notification needs them |
| Player session tokens | Signed identity per request; no Academy-side session store in production |

---

## 3. Relationships

```
Course 1─n CourseVersion 1─n Section 1─n Lesson
CourseVersion n─1 MediaAsset (cover)
Lesson n─1 MediaAsset (video)
Course 1─n Assignment
Assignment 1─n Enrollment   (0..n when a learner joins the target later)
CourseVersion 1─n Enrollment  (pinned)
Enrollment 1─n LessonProgress n─1 Lesson
Enrollment 1─1 CompletionRecord
Enrollment 1─n ReminderLog
Quiz 1─n QuizQuestion 1─n QuizChoice;  Enrollment 1─n QuizAttempt 1─n QuizAttemptAnswer
Organization ─n AuditEvent / NotificationLog / PermissionGrant
```

---

## 4. Invariants: who enforces what

| Invariant | Enforced by |
|---|---|
| Tenant isolation on every read | `for_org` (service/selector) + meta-test |
| One published version per course | Partial unique index |
| Published version content is frozen | Triggers on `CourseVersion`/`Section`/`Lesson` |
| `target_ref` null iff target is the organization | `CHECK` |
| One active enrollment per learner per course | Partial unique index |
| Completion requires every required lesson complete | Service (`complete_enrollment`) |
| Progress ranges are merged and disjoint | Service (`record_heartbeat`) |
| Completion and audit rows cannot change | Triggers |
| Side effects happen at most once | `NotificationLog`/`ReminderLog` unique keys |
| Every video lesson has a `ready` asset before publish | Publish service (`publish_version`) |
| A version has ≥ 2 sections and ≥ 2 lessons | Publish service |
| Last active admin cannot be revoked | Grant service, inside the transaction |

---

## 5. State machines

**CourseVersion:** `draft → published → archived`. `published` requires §4 publish checks.
No reverse transitions.

**MediaAsset:**
```
awaiting_upload ──(presigned PUT + stat verify)──> uploaded
uploaded ──(worker picks up)──> processing
processing ──(ffprobe + ffmpeg HLS ok)──> ready
processing ──(error)──> failed ──(retry ≤ 3)──> processing
awaiting_upload ──(24 h stale purge)──> failed(error_code='stale_upload')
```
Only `ready` assets may be attached to a published lesson or streamed.

**Enrollment:** `active → completed`, `active → cancelled`, `completed → active` is never
allowed (a re-assignment creates a new enrollment row after archival).

**Assignment:** `active → cancelled` only; `cancelled` rows are history.

**PermissionGrant:** `active → revoked`; `active → expired` is derived from `expires_at` at
read time, never written.

---

## 6. Video playback authorization

1. Learner calls `POST /enrollments/{id}/lessons/{lesson_id}/playback/`.
2. Service checks: enrollment ownership, tenant, lesson accessible (§7 gating), asset `ready`.
3. Service presigns the variant playlist and rewrites segment/variant URIs with presigned
   URLs, TTL `max(30 min, 3 × duration)`, key-scoped to that asset prefix.
4. Response is `private, no-store`. URLs are never cached or logged.

---

## 7. Progress, gating and completion algorithm (normative)

This is the specification REQ-09 is tested against. Constants live in
`academy/settings`-independent `academy/progress.py` as module constants so tests can patch them.

### 7.1 Constants
| Name | Value | Purpose |
|---|---|---|
| `HEARTBEAT_INTERVAL_SECONDS` | 15 | Client sends while playing |
| `MAX_HEARTBEAT_GAP_SECONDS` | 60 | Wall-clock elapsed beyond this is not credited |
| `MAX_PLAYBACK_RATE` | 2.0 | Rate is clamped to this for credit |
| `MIN_PLAYBACK_RATE` | 0.5 | Below this, credit is 0 |
| `SKIP_TOLERANCE_SECONDS` | 2.0 | Allowed overshoot of the computed ceiling |
| `RANGE_MERGE_GAP_SECONDS` | 0.5 | Ranges closer than this merge |
| `RANGE_PRECISION` | 0.1 | Seconds stored |
| `DEFAULT_COMPLETE_PERCENT` | 90 | Per-lesson `required_watch_percent` default |

### 7.2 Heartbeat request
`POST /api/v1/academy/enrollments/{enrollment_id}/lessons/{lesson_id}/progress/`

```json
{
  "from_seconds": 120.0,
  "to_seconds": 135.0,
  "playback_rate": 1.0
}
```
Server clock only. Client timestamps, durations and ids are ignored.

### 7.3 Server algorithm
1. Lock the `LessonProgress` row (`SELECT … FOR UPDATE`) for the enrollment+lesson,
   creating it on first heartbeat. Reject if the lesson is not accessible (§7.5).
2. `elapsed = now - coalesce(last_heartbeat_at, now)` (0 on the first heartbeat).
   `credit_window = min(elapsed, MAX_HEARTBEAT_GAP_SECONDS)`.
3. `rate = clamp(playback_rate, MIN_PLAYBACK_RATE, MAX_PLAYBACK_RATE)`.
   If `playback_rate < MIN_PLAYBACK_RATE`, credit is 0.
4. `ceiling = position_seconds + credit_window * rate + SKIP_TOLERANCE_SECONDS`.
   On the first heartbeat, `position_seconds` is 0, so only ~2 s may be credited — the
   learner must earn coverage, never declare it.
5. **Skip check:** if `to_seconds > ceiling` → no state change except
   `skip_attempts += 1`, and respond **HTTP 400** `{"code": "progress_skip_rejected",
   "detail": …, "fields": {"allowed_seconds": ceiling}}`. This is the REQ-09 “forward skip
   rejected by server” behavior. `skip_attempts` feeds an abuse metric and is never surfaced
   to the learner as a warning.
6. **Rewind** (`to_seconds <= position_seconds`): accept the position, credit nothing
   (rewatching an already-covered range adds no coverage). Update `last_heartbeat_at`.
7. **Forward within ceiling:** credit the interval
   `[max(from_seconds, position_seconds), to_seconds]`, but never more than
   `credit_window * rate`. If `from_seconds < position_seconds - RANGE_MERGE_GAP_SECONDS`,
   the gap between `position_seconds` and `from_seconds` is **not** credited.
8. Merge the credited interval into `watched_ranges`:
   sort by start; merge when `next.start - current.end <= RANGE_MERGE_GAP_SECONDS`; clamp to
   `[0, duration_seconds]`; round to 0.1 s. Recompute `watched_seconds` as the exact sum.
   Recompute `frontier_seconds` = end of the first range starting at 0, extended while the
   next range starts within `RANGE_MERGE_GAP_SECONDS`.
9. `position_seconds = to_seconds`, `last_heartbeat_at = now`. Commit.
10. Respond `200` with the authoritative state:
    `{"position_seconds", "watched_seconds", "frontier_seconds", "coverage_percent", "skippable_seconds"}`.
    `coverage_percent = watched_seconds / duration_seconds × 100` (0 when duration is 0).

### 7.4 Idempotency and concurrency
- Replaying an identical heartbeat credits 0 (elapsed is 0 and the ranges already cover it)
  and never corrupts state — merging is monotone.
- One writer per row: the row lock serializes concurrent heartbeats; the second sees the
  updated position and its ceiling. No lost updates, no double credit.
- Heartbeats are **not** audited (volume) and **not** stored individually (ADR-013).

### 7.5 Sequential gating
`lesson_accessible(enrollment, lesson)`:
1. The lesson belongs to `enrollment.course_version` (otherwise 404).
2. Every **required** lesson earlier in reading order
   (`section.position`, then `lesson.position`) that belongs to the same version has
   `completed_at IS NOT NULL`.
3. Non-required lessons are skipped by the chain; they can be opened at any time but do not
   gate later lessons.

Violating (2) returns **403** `{"code": "lesson_locked"}` with
`fields.{"next_lesson_id"}` pointing at the blocking lesson. The API never returns lesson
content for a locked lesson, so the lock is not a UI-only affordance.

### 7.6 Lesson completion
`POST /enrollments/{id}/lessons/{lesson_id}/complete/` (explicit, learner-initiated):
- Requires `watched_seconds / duration_seconds × 100 >= required_watch_percent`.
- `duration_seconds` of 0 (text/pdf lessons) completes on explicit confirmation.
- Idempotent: a second call returns the same completion with `200`.
- Not eligible → **409** `{"code": "lesson_not_eligible"}` with
  `fields.{"coverage_percent", "required_percent"}`.
- Sets `LessonProgress.completed_at`, emits `lesson_completed` on commit.

### 7.7 Enrollment completion
Requires: every required lesson of the pinned version completed, **and** acknowledgment
recorded when `CourseVersion.acknowledgment_required` is true.
Then, inside one transaction: `Enrollment.status = 'completed'`, `completed_at = now`,
insert `CompletionRecord` (unique on enrollment makes a double submit a no-op), and emit
`enrollment_completed` on commit for REQ-10 notifications. Response is `200`, never `201`.

### 7.8 Reminder and escalation evaluation
Daily beat task at 08:00 `ACADEMY_BUSINESS_TZ` (D-002):
- `due_minus_3`, `due`, `due_plus_1` for active enrollments with `due_at` on that day,
  skipping completed/cancelled ones; each insert into `ReminderLog` is the idempotency gate.
- `manager_escalation` at `due + 3 days`: one digest per manager per day covering their
  overdue learners. Manager resolution: `Assignment.assigned_by_ref` when it is a human,
  otherwise Hub `manager` lookup for the learner.
- Re-running the task on the same day writes nothing (unique keys).

### 7.9 Accepted residual risk
A forged client can claim up to `credit_window × rate` per heartbeat, i.e. it must sustain
heartbeats to accumulate coverage. Mitigations: coverage is computed server-side from merged
ranges, `skip_attempts` is tracked, and manager reports expose completion time versus
assignment time. This is documented rather than solved because no browser-side signal is
trustworthy (CHARTER risk table).

---

## 8. Retention and privacy per table

| Table | Retention | Privacy handling |
|---|---|---|
| `CompletionRecord`, `AuditEvent` | 5 y | `export_user_data` / `anonymize_user` cover both |
| `LessonProgress` | Life of enrollment; ranges compacted after 12 mo | Ranges are the learner's own behavior data |
| `NotificationLog`, `ReminderLog` | 90 d | Recipients are refs only |
| `MediaAsset` rows for stale uploads | 24 h then purged | Storage object deleted with the row |
| `Enrollment` | Life of employment + retention period | Anonymization replaces `user_ref` with a tombstone |
| `AccessSuspension` | 5 y with the audit trail | The reason text may carry personal context; export/anonymize cover it |

The meta-test in `academy/tests/test_privacy.py` fails when a model with a `user_ref`-like
column is missing from the export/anonymize registry (REQ-19).

---

## 9. Test obligations produced by this document
- `test_progress_skip_matrix`: forward jump rejected; rewind credits nothing; paused gap does
  not credit beyond `MAX_HEARTBEAT_GAP_SECONDS`; rate 3.0 credits at 2.0; duplicate heartbeat
  is a no-op.
- `test_gating_matrix`: locked lesson returns 403 and no body; non-required lessons skipped.
- `test_completion_idempotency`: double submit yields one `CompletionRecord` and one
  notification key.
- `test_access_suspension`: a suspended user has no effective capability, keeps every stored
  grant, and a lift restores exactly those grants.
- Constraint tests: every `CHECK`/unique index above has one `IntegrityError` test.
- Isolation: every entity here appears in the two-organization fixture.
