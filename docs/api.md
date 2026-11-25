# API — Endpoint Inventory

**Status:** Canonical API surface. `ARCHITECTURE.md` §6 summarizes; this file decides.
**Last updated:** 2026-11-22
**Implements:** REQ-06…REQ-14, REQ-19
**Depends on:** `docs/domain-model.md` (fields, constraints, algorithms), `docs/hub-contract.md`
(webhook and identity), `docs/decisions.md`

## 1. Conventions

- Base path: `/api/v1/academy/` on the Academy service. Through Hub it appears as
  `/academy/api/v1/academy/` (prefix stripped once at the proxy).
- Auth: `ACADEMY_ACCESS_MODE=hub` accepts only a verified Hub identity header; `standalone`
  (development now, production target per D-026) uses a database session with trusted local
  membership. Missing/invalid identity → **401**. Verified but inactive → **403
  `account_inactive`**. Locally suspended → **403 `access_suspended`**. Denied capability →
  **403 `forbidden`**. Wrong tenant → **404** for object routes, empty list for collections.
- Errors: `{"code": "...", "detail": "...", "fields": {...}}`. Codes are stable; `detail` is
  localized human text. Domain exceptions map here in the view layer, never in services.
- Pagination: `page` (1-based) + `page_size` (default 25, max 100), cursor allowed for
  reports. Response `{"count", "next", "previous", "results"}`.
- Personalised responses: `Cache-Control: private, no-store`.
- Mutations: `Idempotency-Key` header accepted on POSTs that create side effects
  (assignments, grants, notifications-triggering actions). Same key + same body returns the
  original result; reused key with a different body → **409 `idempotency_conflict`**.
- CSRF: required on every unsafe browser request (cookie `academy_csrftoken`,
  `Path=/academy/`) — see hub-contract §1.
- Throttles: per identity and per route class (learner reads, heartbeats, management writes,
  exports). Limits live in settings; exceeded → **429 `throttled`** with `Retry-After`.
- Tenant scoping is applied by services/selectors from the verified `organization_id`; no
  endpoint accepts an `organization_id` from the client.

## 2. Capabilities

| Capability | Default holders (Hub role) | Grants |
|---|---|---|
| `academy.learn` | `employee`, `department_manager`, `platform_admin` | addable |
| `academy.manage_content` | `department_manager` (own departments), `platform_admin` (all) | addable |
| `academy.assign` | `department_manager` (own departments), `platform_admin` | addable |
| `academy.view_reports` | `department_manager` (own departments), `platform_admin` | addable |
| `academy.admin` | `platform_admin` | addable, last-admin protected |

Effective capability = Hub role defaults ∪ active grants, unless grants-only mode is enabled.
H1 production sets `ACADEMY_AUTHORIZATION_MODE=grants_only` (D-027): the "Default holders"
column is the compatibility `role_plus_grants` map, not an H1 grant of authority. The first
`academy.admin` is provisioned once through a guarded setup check, and a local suspension
(D-028) removes effective capability without deleting the stored grants.

## 3. Learner endpoints (`academy.learn`)

| Method | Path | Purpose | Notes |
|---|---|---|---|
| GET | `my/courses/` | Courses assigned to me | Includes enrollment status, due date, progress % |
| GET | `my/enrollments/` | My enrollments, filter `status` | Paginated |
| GET | `enrollments/{id}/` | Enrollment detail + outline | Returns sections, lessons, `locked`, `completed`, progress, acknowledgment state |
| POST | `enrollments/{id}/lessons/{lesson_id}/progress/` | Heartbeat | `docs/domain-model.md` §7.2–7.4. 400 `progress_skip_rejected`, 403 `lesson_locked` |
| POST | `enrollments/{id}/lessons/{lesson_id}/complete/` | Complete a lesson | 409 `lesson_not_eligible` when under threshold |
| POST | `enrollments/{id}/lessons/{lesson_id}/playback/` | Presigned HLS URLs | 409 `media_not_ready`; response `private, no-store` |
| POST | `enrollments/{id}/acknowledge/` | Record acknowledgment | Idempotent; 409 `acknowledgment_not_required` |
| POST | `enrollments/{id}/complete/` | Complete the enrollment | 409 `enrollment_incomplete` with blocking lessons; idempotent, returns 200 |
| GET | `me/capabilities/` | Effective capabilities and scopes | Used by both web and API clients |

## 4. Content management (`academy.manage_content`, department-scoped)

| Method | Path | Purpose | Notes |
|---|---|---|---|
| GET | `manage/courses/` | List courses in scope | Filters: `status`, `owner_department_ref`, `q` |
| POST | `manage/courses/` | Create course | Creates a draft version 1 |
| GET | `manage/courses/{id}/` | Course + versions | |
| PATCH | `manage/courses/{id}/` | Title, description, owner department | 409 `course_published_locked` for fields frozen by publish rules |
| POST | `manage/courses/{id}/archive/` | Archive course | Published version becomes `archived` |
| POST | `manage/courses/{id}/versions/` | Clone published version into a new draft | 409 `draft_exists` when a draft is open |
| GET | `manage/versions/{id}/` | Version tree | Sections, lessons, media status |
| POST | `manage/versions/{id}/publish/` | Publish | Validation list in §8; 422 `publish_invalid` with per-item reasons |
| POST | `manage/versions/{id}/discard/` | Delete an unpublished draft | 409 `version_published` |
| GET/POST | `manage/versions/{id}/sections/` | List / create section | Position auto-appended unless supplied |
| PATCH/DELETE | `manage/sections/{id}/` | Rename / delete | Delete allowed only on drafts |
| POST | `manage/versions/{id}/sections/reorder/` | Reorder | Body: ordered id list; 409 on mismatch |
| GET/POST | `manage/sections/{id}/lessons/` | List / create lesson | |
| PATCH/DELETE | `manage/lessons/{id}/` | Edit / delete | |
| POST | `manage/sections/{id}/lessons/reorder/` | Reorder within a section | |
| POST | `manage/media/uploads/` | Create asset + presigned PUT | Body: `kind`, `original_filename`, `content_type`, `size_bytes`; 400 `upload_too_large`, 400 `unsupported_type` |
| POST | `manage/media/{id}/complete/` | Verify upload and enqueue processing | `stat` verify; 409 `upload_missing`, 409 `checksum_mismatch` |
| GET | `manage/media/{id}/` | Asset status | `status`, `error_code`, `renditions` |
| POST | `manage/media/{id}/retry/` | Re-enqueue a failed asset | 409 `retry_limit_reached` |

## 5. Assignment (`academy.assign`)

| Method | Path | Purpose | Notes |
|---|---|---|---|
| GET | `manage/assignments/` | List assignments in scope | Filters: `course`, `target_type`, `active` |
| POST | `manage/assignments/` | Create assignment and expand to enrollments | `Idempotency-Key` required. 422 `target_empty` when expansion yields nobody |
| POST | `manage/assignments/preview/` | Recipient count only | D-017: `{target_type, target_ref}` → `{count, capped: bool}`; no identities, cap 5,000 |
| DELETE | `manage/assignments/{id}/` | Cancel | Soft cancel + cancel active enrollments with reason `unassigned` |
| GET | `manage/courses/{id}/enrollments/` | Enrollment roster | Filters: `status`, `overdue`, `department_ref` |
| POST | `manage/enrollments/{id}/cancel/` | Cancel one enrollment | Audited |
| POST | `manage/enrollments/{id}/complete/` | Admin override completion | `academy.admin`; `method='admin_override'`; audited with reason |

## 6. Reports (`academy.view_reports`)

| Method | Path | Purpose | Notes |
|---|---|---|---|
| GET | `manage/reports/summary/` | Completion %, overdue count, average time | Grouped by `course` or `department_ref` |
| GET | `manage/reports/overdue/` | Overdue learners | Sorted by days overdue |
| GET | `manage/reports/completion/` | Per-learner completion rows | Paginated, cursor supported |
| GET | `manage/reports/export.csv` | CSV export | Neutralizes formula injection (`= + - @ \t \r`); `Content-Disposition: attachment`; audited |

All report queries are department-scoped for `department_manager`. Query count is asserted
in tests (no N+1 over enrollments).

## 7. Administration (`academy.admin`)

| Method | Path | Purpose | Notes |
|---|---|---|---|
| GET | `manage/grants/` | List grants | Filters: `user_ref`, `capability`, `state` (`active \| expired \| revoked`) |
| POST | `manage/grants/` | Grant | `Idempotency-Key`; audited in the same transaction |
| DELETE | `manage/grants/{id}/` | Revoke | 409 `last_admin` when it would remove the last active admin; audited |
| GET | `manage/access/` | Local suspensions | Filters: `user_ref`, `state` (`suspended \| lifted`) |
| POST | `manage/access/{user_ref}/suspend/` | Suspend Academy access locally | `academy.admin` in scope; reason required; audited `access.suspended`; stored grants kept |
| POST | `manage/access/{user_ref}/lift/` | Lift a local suspension | Reason required; audited `access.lifted`; never changes Hub membership |
| GET | `manage/settings/` | Organization settings | Completion threshold default, retention values, grants-only mode |
| PATCH | `manage/settings/` | Update settings | Audited |
| GET | `manage/audit/` | Audit search | Filters: `action`, `object_type`, `object_id`, `actor_ref`, date range |
| POST | `manage/users/{user_ref}/export/` | Privacy export | REQ-19; audited; returns a JSON bundle |
| POST | `manage/users/{user_ref}/anonymize/` | Anonymize | Requires reason; audited; irreversible |

## 8. Publish validation (422 `publish_invalid`)

`fields.items[]` carries `{code, section_id?, lesson_id?}`. Codes:
`too_few_sections` (<2), `too_few_lessons` (<2), `section_without_lessons`,
`lesson_without_title`, `lesson_media_missing`, `lesson_media_not_ready`,
`text_lesson_empty`, `position_gap`, `cover_media_invalid`.

## 9. Internal and operational routes (not proxied to browsers)

| Method | Path | Purpose | Notes |
|---|---|---|---|
| POST | `/internal/hub/webhooks/` | `member_changed`, `member_deactivated` | Signed per hub-contract §4; not exposed at the Hub |
| GET | `/healthz` | Liveness/readiness | Checks DB, Redis, storage; 200/503 only |
| GET | `/api/schema` | OpenAPI 3 document | Development/staging route; the production deployment keeps it disabled (T-024 check) |

## 10. Web pages (server-rendered, same services)

| Route (under `/academy/`) | Screen | Capability |
|---|---|---|
| `/` | A · Academy (course list) | `learn` or `manage_content` |
| `/manage/courses/new/` | B · New course | `manage_content` |
| `/manage/courses/{id}/edit/` | C · Lessons and upload | `manage_content` |
| `/manage/assignments/new/` | D · Assignment dialog | `assign` |
| `/learn/{enrollment_id}/` | E · Course player | `learn` + ownership |
| `/manage/team/` | F · Team training | `view_reports` |
| `/manage/permissions/` | G · Permissions | `admin` |
| `/manage/audit/` | S1 · Audit log | `admin` |
| `/dashboard/` | L1 · My dashboard | `learn` |
| `/my/courses/` | L2 · My courses | `learn` |
| `/my/courses/{course_id}/` | L3 · Course details | `learn` + enrolled |
| `/my/achievements/` | L4 · Achievements | `learn` |
| `/login/` | X1 · Local sign-in | `standalone` mode only |
| `/preview/…` | Preview showcase (dev only) | Dev profile only |

The web layer derives everything from the same services and selectors as the API; it must
not add business rules.

## 11. Error codes (complete list)
`validation_error` 400 · `progress_skip_rejected` 400 · `upload_too_large` 400 ·
`unsupported_type` 400 · `unauthorized` 401 · `account_inactive` 403 · `forbidden` 403 ·
`lesson_locked` 403 · `access_suspended` 403 · `not_found` 404 · `method_not_allowed` 405 · `idempotency_conflict` 409 · `draft_exists` 409 ·
`version_published` 409 · `course_published_locked` 409 · `position_mismatch` 409 ·
`upload_missing` 409 ·
`checksum_mismatch` 409 · `retry_limit_reached` 409 · `media_not_ready` 409 ·
`lesson_not_eligible` 409 · `enrollment_incomplete` 409 · `acknowledgment_not_required` 409 ·
`last_admin` 409 · `publish_invalid` 422 · `target_empty` 422 · `throttled` 429 ·
`unavailable` 503.

## 12. Test obligations
Every endpoint gets the matrix from `docs/skills/api-endpoint.md`: success, validation error,
401 anonymous, 403 capability, other-tenant 404, other-user object, pagination, and a
query-count assertion for lists. Heartbeat and completion add the matrices in
`docs/domain-model.md` §9.
