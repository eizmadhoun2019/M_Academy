# API — Contracts, Endpoints and Compatibility

**Status:** Canonical API surface. `ARCHITECTURE.md` §8 summarizes; this file decides.
**Last updated:** 2026-11-25
**Implements:** REQ-06…REQ-14, REQ-19, REQ-22…REQ-26, REQ-28
**Depends on:** `docs/domain-model.md`, `docs/access-control.md`, `docs/security.md`,
`docs/hub-contract.md` (optional webhook/identity), `docs/decisions.md`

## 1. Conventions
- Base path `/api/v1/academy/` on Academy's own origin (D-035). The route namespace is
  `academy_api`; web routes are separate namespaces (`public`, `app`, `manage`, `platform`).
- **Authentication:** browser session cookie (`m_academy_sessionid`) + CSRF for unsafe methods;
  unauthenticated → **401 `unauthorized`**. Verified but inactive/suspended account → **403
  `account_inactive`**; inactive membership → **403 `membership_inactive`**; company suspended →
  **403 `organization_suspended`**; locally suspended membership → **403 `access_suspended`**.
  Hub-signed identity is accepted only when the optional integration is explicitly enabled
  (`ACADEMY_HUB_ENABLED=true`) and is verified per `docs/hub-contract.md` §2.
- **Company context:** server-side and derived from the caller's single active membership
  (`UNIQUE (user_id)`, D-043). Endpoints never accept `organization_id` as authority; a body/query
  value is ignored or rejected, and there is no switch endpoint. Platform-only accounts have no
  membership: platform routes carry an explicit company id and require a `platform.*` permission
  (writes inside read-only platform access → 403). A tenant request with no active membership →
  **403 `membership_inactive`**.
- **Authorization:** each operation declares one permission from `docs/access-control.md` §2 and
  its allowed scopes. Denied → **403 `forbidden`**. Objects outside the caller's company or scope
  → **404 `not_found`** (never 403), so existence does not leak.
- Errors: `{"code": "...", "detail": "...", "fields": {...}, "request_id": "..."}`. Codes are
  stable; `detail` is localized. Domain exceptions map in the view layer only.
- Pagination: `page` (1-based) + `page_size` (default 25, max 100); `{"count","next","previous",
  "results"}`. Reports may use a cursor.
- Personalised responses: `Cache-Control: private, no-store`.
- Mutations: `Idempotency-Key` required on side-effect POSTs (assignments, invitations, grants,
  notifications-triggering actions). Same key + same body replays the result; different body →
  **409 `idempotency_conflict`**.
- CSRF required on every unsafe browser request (cookie `academy_csrftoken`, `Path=/`).
- Throttles per identity and route class; exceeded → **429 `throttled`** + `Retry-After`.
- All timestamps ISO-8601 UTC (`Z`); display conversion happens in the UI using the company/user
  time zone.
- API versioning: additive fields and new endpoints within `v1`; a breaking change requires `v2`,
  a documented migration window of at least one minor release, and owner approval (REQ-28).

## 2. Effective access payload
`GET /me/capabilities/` returns the server-computed authority used by the UI. Clients must not
infer authority from role names.

```json
{
  "user": {"id": "uuid", "display_name": "...", "email": "...", "preferred_language": "ar"},
  "organization": {"id": "uuid", "name": "...", "timezone": "Asia/Riyadh", "status": "active"},
  "membership": {"id": "uuid", "status": "active", "department_id": "uuid"},
  "permissions": [{"code": "academy.report.view", "scope": "DEPARTMENT", "department_ids": ["uuid"]}],
  "platform_permissions": ["platform.organization.view"],
  "mfa_enabled": true,
  "platform_access": false
}
```
`permissions` is the union after role, grant, scope and suspension evaluation; an empty list is
valid. `platform_access` is true only inside an audited read-only platform-access session.
`organization` and `membership` are `null` for a platform-only account; platform screens use the
explicit company id in their route and never fabricate a membership.

## 3. Authentication and account endpoints (`/api/v1/academy/auth/`)
| Method | Path | Purpose | Notes |
|---|---|---|---|
| POST | `login/` | Email + password (+ `mfa_code`) | 200 with session and `redirect` (the first dashboard the permissions allow); 401 `mfa_required` + `challenge_id` when TOTP is needed; generic 401 `invalid_credentials`; 429 `throttled` |
| POST | `mfa/verify/` | Complete an MFA challenge | 5-minute single-use challenge; 401 `mfa_invalid` |
| POST | `logout/` | End the session | Idempotent; audited |
| POST | `password/reset/request/` | Send reset mail | Always 202 `accepted` (no account enumeration) |
| POST | `password/reset/confirm/` | Consume token + set password | 400 `token_invalid`; revokes other sessions; audited |
| POST | `password/change/` | Change own password | Current password required; revokes other sessions |
| POST | `email/verify/request/` | Resend verification | Throttled; 202 always |
| POST | `email/verify/confirm/` | Consume verification token | 400 `token_invalid` |
| POST | `invitations/accept/` | Accept company invitation | Token + password + display name; creates/activates account and membership; 400 `invitation_invalid`; 409 `already_member` if the account already belongs to another company |
| GET | `sessions/` | List own sessions | Device family, last seen, current flag |
| DELETE | `sessions/{id}/` | Revoke one session | Ownership rechecked; audited |
| POST | `mfa/enroll/` | Start TOTP enrolment | Password re-entry; returns secret + otpauth URI once |
| POST | `mfa/confirm/` | Confirm TOTP + receive recovery codes | Codes shown once |
| POST | `mfa/disable/` | Disable MFA | Password + TOTP/recovery code; audited |

`GET /me/` (profile) and `PATCH /me/` (display name, preferred language) are the only
self-service profile writes. Email change is a separate verified flow (`POST /me/email/change/`
→ confirm token) and revokes other sessions.

## 4. Company context (read-only)
| Method | Path | Purpose | Notes |
|---|---|---|---|
| GET | `me/organization/` | The caller's single company | Company name, status, time zone and the caller's department names; `null` for a platform-only account. Never lists other companies or members. |

There is no company-selection, switching or membership-list endpoint for a normal user. The
session stores only the user; the server resolves the company from the membership on every
request. Platform administrators choose a company only inside `platform/organizations/{id}/…`.

## 5. Learner endpoints (`academy.learn`, SELF)
| Method | Path | Purpose | Notes |
|---|---|---|---|
| GET | `my/courses/` | Courses assigned to me | Enrollment status, due date, progress % |
| GET | `my/enrollments/` | My enrollments, filter `status` | Paginated |
| GET | `enrollments/{id}/` | Enrollment detail + outline | Sections, lessons, `locked`, `completed`, progress, acknowledgment |
| POST | `enrollments/{id}/lessons/{lesson_id}/progress/` | Heartbeat | `docs/domain-model.md` §7.2–7.4; 400 `progress_skip_rejected`, 403 `lesson_locked` |
| POST | `enrollments/{id}/lessons/{lesson_id}/complete/` | Complete a lesson | 409 `lesson_not_eligible` |
| POST | `enrollments/{id}/lessons/{lesson_id}/playback/` | Presigned HLS URLs | 409 `media_not_ready`; `private, no-store` |
| POST | `enrollments/{id}/acknowledge/` | Record acknowledgment | Idempotent; 409 `acknowledgment_not_required` |
| POST | `enrollments/{id}/complete/` | Complete enrollment | 409 `enrollment_incomplete` with blocking lessons; returns 200 |

Every route rechecks `enrollment.membership_id == principal.membership_id` and the active
company; a foreign enrollment is 404.

## 6. Content management (`academy.content.view/manage/publish`, `academy.media.manage`)
| Method | Path | Purpose | Permission | Notes |
|---|---|---|---|---|
| GET | `manage/courses/` | List courses in scope | `academy.content.view` | Filters `status`, `owner_department_id`, `q` |
| POST | `manage/courses/` | Create course | `academy.content.manage` | Creates draft version 1 |
| GET | `manage/courses/{id}/` | Course + versions | `academy.content.view` | |
| PATCH | `manage/courses/{id}/` | Title/description/owner department | `academy.content.manage` | 409 `course_published_locked` for frozen fields |
| POST | `manage/courses/{id}/archive/` | Archive course | `academy.content.publish` | Published version becomes archived |
| POST | `manage/courses/{id}/versions/` | Clone published version to draft | `academy.content.manage` | 409 `draft_exists` |
| GET | `manage/versions/{id}/` | Version tree | `academy.content.view` | |
| POST | `manage/versions/{id}/publish/` | Publish | `academy.content.publish` | 422 `publish_invalid` (§9) |
| POST | `manage/versions/{id}/discard/` | Delete an unpublished draft | `academy.content.manage` | 409 `version_published` |
| GET/POST | `manage/versions/{id}/sections/` | List/create section | `academy.content.manage` | |
| PATCH/DELETE | `manage/sections/{id}/` | Rename/delete | `academy.content.manage` | Draft only |
| POST | `manage/versions/{id}/sections/reorder/` | Reorder | `academy.content.manage` | 409 `position_mismatch` |
| GET/POST | `manage/sections/{id}/lessons/` | List/create lesson | `academy.content.manage` | |
| PATCH/DELETE | `manage/lessons/{id}/` | Edit/delete | `academy.content.manage` | |
| POST | `manage/sections/{id}/lessons/reorder/` | Reorder | `academy.content.manage` | |
| POST | `manage/media/uploads/` | Asset + presigned PUT | `academy.media.manage` | 400 `upload_too_large`, `unsupported_type` |
| POST | `manage/media/{id}/complete/` | Verify and enqueue | `academy.media.manage` | 409 `upload_missing`, `checksum_mismatch` |
| GET | `manage/media/{id}/` | Asset status | `academy.content.view` | |
| POST | `manage/media/{id}/retry/` | Re-enqueue | `academy.media.manage` | 409 `retry_limit_reached` |

Department-scoped callers see only courses whose `owner_department_id` is in scope; general
courses (`NULL`) are readable but only COMPANY scope may edit or publish them.

## 7. Assignments (`academy.assignment.view/manage`)
| Method | Path | Purpose | Notes |
|---|---|---|---|
| GET | `manage/assignments/` | List in scope | Filters `course`, `target_type`, `active` |
| POST | `manage/assignments/` | Create + expand | `Idempotency-Key`; 422 `target_empty` |
| POST | `manage/assignments/preview/` | Recipient count only | D-017: `{target_type, target_id?}` → `{count, capped}`; cap 5,000 |
| DELETE | `manage/assignments/{id}/` | Cancel | Soft cancel + cancel enrollments `unassigned` |
| GET | `manage/courses/{id}/enrollments/` | Roster | Filters `status`, `overdue`, `department_id` |
| POST | `manage/enrollments/{id}/cancel/` | Cancel one | Audited |
| POST | `manage/enrollments/{id}/complete/` | Admin override | Requires `academy.member.manage` at COMPANY; body `{reason}`; `method='admin_override'`; audited |

Scope rules: a department target must be inside the caller's scope; a membership target must
belong to a department in scope; `role` and `organization` targets span the company and require
COMPANY scope (otherwise 403). Out-of-scope targets/assignments answer 404. Preview and write
share one selector. A missing/archived published version → 409 `course_not_published`.

## 8. Reports (`academy.report.view/export`)
| Method | Path | Purpose | Notes |
|---|---|---|---|
| GET | `manage/reports/summary/` | Completion %, overdue, average time | Group by `course` or `department` |
| GET | `manage/reports/overdue/` | Overdue learners | Sorted by days overdue |
| GET | `manage/reports/completion/` | Per-learner rows | Cursor pagination |
| GET | `manage/reports/export.csv` | CSV export | Requires `academy.report.export`; formula-neutralized; audited |
| GET | `platform/reports/summary/` | Cross-company aggregate | Requires `platform.organization.view`; explicit `organization_id` filter; never mixes companies without a label |

Reports use `docs/reports.md` formulas. Department scope is applied before aggregation; an
out-of-scope filter is 403, never an empty list. `from > to` → 400 `invalid_range`.

## 9. Publish validation (422 `publish_invalid`)
`fields.items[]` carries `{code, section_id?, lesson_id?}`:
`too_few_sections` (<2), `too_few_lessons` (<2), `section_without_lessons`,
`lesson_without_title`, `lesson_media_missing`, `lesson_media_not_ready`, `text_lesson_empty`,
`position_gap`, `cover_media_invalid`.

## 10. Company administration (`academy.member.*`, `academy.department.manage`, `academy.role.manage`, `academy.grant.manage`, `academy.audit.view`, `academy.settings.manage`)
| Method | Path | Purpose | Permission |
|---|---|---|---|
| GET | `manage/members/` | Members, filters `status`, `department_id`, `q` | `academy.member.view` |
| POST | `manage/invitations/` | Invite by email with role(s) + department | `academy.member.manage`; 409 `already_member` when the email already has any membership |
| POST | `manage/invitations/{id}/resend/` | Re-issue (invalidates previous token) | `academy.member.manage` |
| DELETE | `manage/invitations/{id}/` | Revoke | `academy.member.manage` |
| GET | `manage/members/{id}/` | Membership detail | `academy.member.view` |
| PATCH | `manage/members/{id}/` | Department/status (activate/suspend) | `academy.member.manage`; reason required for suspension |
| DELETE | `manage/members/{id}/` | Remove membership | `academy.member.manage`; 409 `last_admin`; cancels enrollments; row retained (same-company restore only before anonymization) |
| GET/POST | `manage/members/{id}/roles/` | List/assign roles | `academy.role.manage`; no escalation |
| DELETE | `manage/members/{id}/roles/{assignment_id}/` | Revoke | `academy.role.manage`; 409 `last_admin` |
| GET/POST | `manage/departments/` | Tree/create | `academy.member.view` / `academy.department.manage` |
| PATCH/DELETE | `manage/departments/{id}/` | Rename/re-parent/archive | `academy.department.manage` |
| GET/POST | `manage/roles/` | Company roles | `academy.role.manage` |
| PATCH/DELETE | `manage/roles/{id}/` | Edit/delete custom role | `academy.role.manage`; system roles 409 `role_system` |
| GET/PUT | `manage/roles/{id}/permissions/` | Replace permission set | `academy.role.manage`; platform permissions rejected |
| GET/POST | `manage/grants/` | Exceptional grants | `academy.grant.manage`; reason + expiry required |
| DELETE | `manage/grants/{id}/` | Revoke | `academy.grant.manage` |
| GET | `manage/audit/` | Audit search | `academy.audit.view`; filters action/object/actor/date |
| GET/PATCH | `manage/settings/` | Company settings | `academy.settings.manage` |
| POST | `manage/users/{id}/export/` | Privacy export | `academy.member.manage`; audited; JSON bundle |
| POST | `manage/users/{id}/anonymize/` | Anonymize | `academy.member.manage`; reason required; irreversible; audited |

## 11. Platform administration (`platform.*`)
| Method | Path | Purpose | Permission |
|---|---|---|---|
| GET/POST | `platform/organizations/` | List/create companies | `platform.organization.view` / `platform.organization.manage` |
| GET | `platform/organizations/{id}/` | Company detail + counts | `platform.organization.view` |
| PATCH | `platform/organizations/{id}/` | Name, settings | `platform.organization.manage` |
| POST | `platform/organizations/{id}/suspend/` | Suspend | `platform.organization.manage`; reason required |
| POST | `platform/organizations/{id}/reactivate/` | Reactivate | `platform.organization.manage` |
| POST | `platform/organizations/{id}/archive/` | Archive | `platform.organization.manage`; blocked while active members exist |
| GET | `platform/users/` | Platform users | `platform.user.manage` |
| POST | `platform/users/{id}/roles/` | Assign platform role | `platform.user.manage`; 409 `last_admin` |
| DELETE | `platform/users/{id}/roles/{assignment_id}/` | Revoke | `platform.user.manage`; 409 `last_admin` |
| POST | `platform/organizations/{id}/access/` | Start audited read-only access | `platform.organization.access`; returns context + audit id |
| DELETE | `platform/organizations/{id}/access/` | End access | `platform.organization.access` |
| GET | `platform/audit/` | Platform audit search | `platform.audit.view` |
| GET | `platform/settings/` | Platform settings + integration flags | `platform.settings.manage` |
| GET | `platform/reports/summary/` | Per-company aggregate (explicit filter) | `platform.organization.view` |

Platform access is read-only. Write attempts inside it → **403 `platform_access_readonly`**; every
start/end is audited with the company id.

## 12. Internal and operational routes
| Method | Path | Purpose | Notes |
|---|---|---|---|
| POST | `/internal/hub/webhooks/` | `member_changed`, `member_deactivated` | Only mounted when Hub is enabled; signed per hub-contract §4; 404 otherwise |
| GET | `/healthz` | Liveness | Process; 200 while serving |
| GET | `/readyz` | Readiness | DB, Redis, storage, migrations; 200/503 only |
| GET | `/api/schema` | OpenAPI 3 | Development/staging; disabled in production by configuration |
| GET | `/metrics` | Prometheus | Internal network only |

## 13. Web pages (server-rendered, same services)
| Route | Screen | Permission |
|---|---|---|
| `/` | P1 · Public home | public |
| `/about/`, `/programmes/`, `/contact/`, `/privacy/`, `/terms/` | P2–P5 · Public pages | public |
| `/academy/login/`, `/academy/password/reset/`, `/academy/password/reset/{token}/`, `/academy/verify/{token}/`, `/academy/invite/{token}/` | X1, X3–X5 | public (rate-limited) |
| `/academy/denied/` | X6 · Access denied | any authenticated/blocked state |
| `/academy/` | Application entry → redirect to the first dashboard permitted (L1 or platform) | authenticated |
| `/academy/dashboard/` | L1 · My dashboard | `academy.learn` |
| `/academy/my/courses/` | L2 · My courses | `academy.learn` |
| `/academy/my/courses/{course_id}/` | L3 · Course details | `academy.learn` + enrolled |
| `/academy/my/achievements/` | L4 · Achievements | `academy.learn` |
| `/academy/learn/{enrollment_id}/` | E · Course player | `academy.learn` + owner |
| `/academy/manage/courses/…` | B, C · Course authoring | `academy.content.*` |
| `/academy/manage/assignments/…` | D · Assignment | `academy.assignment.*` |
| `/academy/manage/reports/` | F · Team training | `academy.report.view` |
| `/academy/manage/members/` | N1 · Members & invitations | `academy.member.*` |
| `/academy/manage/roles/` | N2 · Roles & grants | `academy.role.manage` |
| `/academy/manage/departments/` | N3 · Departments | `academy.department.manage` |
| `/academy/manage/settings/` | N4 · Company settings | `academy.settings.manage` |
| `/academy/manage/audit/` | S1 · Company audit | `academy.audit.view` |
| `/academy/platform/` | N5 · Platform overview | `platform.organization.view` |
| `/academy/platform/organizations/…` | N6 · Companies | `platform.organization.*` |
| `/academy/platform/users/` | N7 · Platform users | `platform.user.manage` |
| `/academy/platform/settings/` | N8 · Platform settings | `platform.settings.manage` |
| `/academy/platform/audit/` | S2 · Platform audit | `platform.audit.view` |
| `/academy/preview/…` | Preview showcase (dev only) | Dev profile only |

The web layer derives everything from the same services/selectors as the API and adds no
business rules.

## 14. Error codes (complete list)
`validation_error` 400 · `invalid_range` 400 · `progress_skip_rejected` 400 ·
`upload_too_large` 400 · `unsupported_type` 400 · `token_invalid` 400 ·
`invitation_invalid` 400 · `invalid_credentials` 401 · `mfa_required` 401 · `mfa_invalid` 401 ·
`unauthorized` 401 · `account_inactive` 403 · `membership_inactive` 403 ·
`organization_suspended` 403 · `forbidden` 403 · `lesson_locked` 403 ·
`access_suspended` 403 · `platform_access_readonly` 403 · `not_found` 404 ·
`method_not_allowed` 405 · `idempotency_conflict` 409 · `draft_exists` 409 ·
`version_published` 409 · `course_published_locked` 409 · `position_mismatch` 409 ·
`upload_missing` 409 · `checksum_mismatch` 409 · `retry_limit_reached` 409 ·
`media_not_ready` 409 · `lesson_not_eligible` 409 · `enrollment_incomplete` 409 ·
`acknowledgment_not_required` 409 · `last_admin` 409 · `role_system` 409 ·
`course_not_published` 409 · `already_member` 409 · `escalation_denied` 403 ·
`publish_invalid` 422 · `target_empty` 422 · `throttled` 429 · `unavailable` 503.

## 15. Compatibility and test obligations
- Additive changes only in `v1`; removing/renaming a field or changing an error code requires
  `v2` and owner approval. Deprecations are announced in `LOG.md` and kept for one minor release.
- Every endpoint runs the matrix in `docs/skills/api-endpoint.md`: success, validation error,
  anonymous 401, wrong permission 403, other-company 404, other-user object, pagination, and a
  query-count assertion for lists.
- Auth endpoints additionally test enumeration, throttling, token replay, MFA challenge replay,
  session revocation and the dev-login-absent-in-production assertion.
- The OpenAPI schema must have zero warnings (G5) and is regenerated in CI; a changed schema is
  reviewed as a contract change.
