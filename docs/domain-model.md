# DOMAIN MODEL — Entities, Constraints, State Machines and the Progress Algorithm

**Status:** Canonical schema specification. `ARCHITECTURE.md` §5/§7 summarizes; this file decides.
**Last updated:** 2026-11-25
**Implements:** REQ-03, REQ-06…REQ-14, REQ-19, REQ-21…REQ-25, REQ-28
**Depends on:** `docs/decisions.md` (D-003, D-013…D-017, D-031…D-042), `docs/access-control.md`,
`docs/security.md`, `docs/api.md`, `docs/hub-contract.md`

Any change here follows `docs/skills/model-change.md`. PostgreSQL is the only supported
database (ADR-008); SQLite is never used, not even in tests.

---

## 1. Conventions

### 1.1 Base models
Every **tenant-owned** model subclasses `academy.models.TenantModel` (meta-test enforced):

| Column | Type | Rules |
|---|---|---|
| `id` | `uuid` | Primary key, generated in Python (v4 today; v7 for new tables when D-041's condition is met) |
| `organization_id` | `uuid` FK → `Organization` | NOT NULL, `ON DELETE PROTECT` |
| `created_at` | `timestamptz` | NOT NULL, set once, `timezone.now()` only |
| `updated_at` | `timestamptz` | NOT NULL, auto |

Global models subclass `academy.models.BaseModel` (id + timestamps, no organization):
`Organization`, `User`, `AccountToken`, `MFADevice`, `RecoveryCode`, `UserSession`,
`Permission`, and `AuditEvent` (nullable organization). `Role` is global for system templates
(`organization_id IS NULL`) and tenant-owned for company roles; that exception is declared in
the model and in the meta-test allowlist.

- Managers: `objects` (unrestricted, migrations and tests only) and
  `TenantModel.objects.for_org(organization_id)`. Every runtime read goes through `for_org` or a
  selector that requires the organization.
- Every non-unique index on a tenant table starts with `organization_id`.
- Foreign keys to tenant entities use **composite keys** `(organization_id, <parent>_id)` where
  the parent is tenant-owned, so a child cannot reference another company's row. This requires a
  `UNIQUE (organization_id, id)` on each referenced parent.
- Enumerations are Django `TextChoices` **plus** a `CheckConstraint` (no DB enum types, so
  adding a value is a plain code change).
- Lifecycle is soft for history-bearing rows (company archive, membership removed, account
  anonymized). Hard deletion is a platform command with audit and a backup check.

### 1.2 Reference columns after the identity migration
| Column | Meaning |
|---|---|
| `*_id` FK | Normal relation (account, membership, department, role, media) |
| `actor_id` (audit/logs) | UUID snapshot of the acting user; immutable, survives anonymization |
| `dedupe_key` | Idempotency key of an outbound side effect |
| `user_ref` | **Legacy only** until T-028 completes; mapped to `User.id` / `Membership.id`; no new column may use it |

Names and email **are stored** on `User` as minimal authentication data (D-037); they are
never copied into business tables, audit payloads, logs or metrics.

---

## 2. Entities

Order is the migration order. “Derived” means computed and never stored.

### 2.0 Identity and tenancy

#### 2.0.1 `Organization` (global)
| Field | Type | Null | Default | Constraints / notes |
|---|---|---|---|---|
| `name_ar` | varchar(200) | no | — | Non-blank |
| `name_en` | varchar(200) | yes | `NULL` | Falls back to `name_ar` |
| `slug` | varchar(60) | no | — | `UNIQUE`, lowercase `[a-z0-9-]`, immutable after creation |
| `status` | varchar(16) | no | `active` | `active \| suspended \| archived` |
| `default_language` | varchar(5) | no | `ar` | `ar \| en` |
| `timezone` | varchar(64) | no | `Asia/Riyadh` | Valid IANA zone (validated) |
| `reminder_hour` | smallint | no | `8` | `CHECK BETWEEN 0 AND 23`, local time |
| `sender_name` | varchar(120) | yes | `NULL` | Mail from-name; platform default if null |
| `settings` | jsonb | no | `'{}'` | Reserved; typed fields above are authoritative |
| `archived_at` | timestamptz | yes | `NULL` | NOT NULL iff `status='archived'` |

Indexes: `UNIQUE (slug)`, `(status)`. No hard delete while any tenant row exists.

#### 2.0.2 `User` (global account)
| Field | Type | Null | Default | Constraints / notes |
|---|---|---|---|---|
| `email` | citext | no | — | `UNIQUE`, normalized lowercase; login attribute, **not** a relation key |
| `display_name` | varchar(150) | no | — | Trimmed, non-blank |
| `password` | varchar(128) | no | — | Django Argon2 hash; never logged |
| `status` | varchar(16) | no | `active` | `unverified \| active \| suspended \| deactivated` |
| `is_email_verified` | boolean | no | `false` | Set by verification or invitation acceptance |
| `preferred_language` | varchar(5) | no | `ar` | `ar \| en` |
| `last_login_at` | timestamptz | yes | `NULL` | Server clock |
| `password_changed_at` | timestamptz | yes | `NULL` | Used to revoke older sessions |
| `anonymized_at` | timestamptz | yes | `NULL` | PII replaced; row kept for history |
| `legacy_ref` | varchar(64) | yes | `NULL` | Migration only (T-026 CP2): the imported `user_ref`; `UNIQUE` when set; dropped at contract (M6) |
| `must_set_email` | boolean | no | `false` | Migration only (T-026 CP2): an imported account with no address keeps a non-deliverable placeholder and cannot sign in until T-027 sets one |

Constraints: `CHECK (status IN (...))`, unique lower(email) (citext), unique `legacy_ref` where
not null. Index `(status)`.
`email` is replaced with `anon+<uuid>@invalid` on anonymization; `display_name` with
`Deleted user`. One account holds at most one membership; the account is never company-scoped.
A platform-only account (`PlatformRoleAssignment`) may have **zero** memberships and needs no
synthetic company row.

#### 2.0.3 `Membership` (tenant)
| Field | Type | Null | Default | Constraints / notes |
|---|---|---|---|---|
| `user_id` | uuid FK → User | no | — | `ON DELETE PROTECT` |
| `status` | varchar(16) | no | `invited` | `invited \| active \| suspended \| removed` |
| `joined_at` | timestamptz | yes | `NULL` | Set on activation |
| `removed_at` | timestamptz | yes | `NULL` | Required iff `removed` |
| `invited_by_id` | uuid FK → User | yes | `NULL` | `SET NULL` |
| `department_id` | uuid FK → Department | yes | `NULL` | Composite tenant FK; primary department |
| `roles` | jsonb | no | `[]` | **Provisional (T-027 CP2):** the company role codes an invitation granted; read when a session is created. T-028 replaces it with `RoleAssignment` and migrates the codes |

Constraints: **`UNIQUE (user_id)`** (D-043 — one company per account; this is the authoritative
cardinality constraint), `UNIQUE (organization_id, id)`,
`CHECK (status='removed') = (removed_at IS NOT NULL)`, `CHECK (status<>'active' OR joined_at IS NOT NULL)`.
Indexes: `(organization_id, status)`, `(organization_id, department_id)`.
Membership history survives removal; training rows keep pointing at it with `PROTECT`. The unique
index also makes the per-request company lookup a single indexed row, so the simplification adds
no query or join. The service checks before insert and maps a database `IntegrityError` to **409 `already_member`**; tests cover
both the API and a direct duplicate insert. Platform administrators have no row here.

#### 2.0.4 `Department` (tenant)
| Field | Type | Null | Default | Constraints / notes |
|---|---|---|---|---|
| `name_ar` | varchar(200) | no | — | Non-blank |
| `name_en` | varchar(200) | yes | `NULL` | |
| `parent_id` | uuid FK → Department | yes | `NULL` | Composite `(organization_id, parent_id)`; no cycles (service) |
| `status` | varchar(16) | no | `active` | `active \| archived` |
| `position` | integer | no | `0` | Sibling display order |
| `legacy_ref` | varchar(64) | yes | `NULL` | Migration only (T-026 CP2): the imported `department_ref`, `UNIQUE` per company when set; dropped at contract (M6) |

Constraints: `UNIQUE (organization_id, id)`, `UNIQUE (organization_id, parent_id, name_ar)`,
`UNIQUE (organization_id, legacy_ref)` where `legacy_ref` is not null,
`CHECK (parent_id <> id)`. Index `(organization_id, status)`.
Depth limit 5 (service). Archiving requires no active memberships or assignments in the subtree.

#### 2.0.5 `Permission` (global catalogue)
| Field | Type | Null | Default | Constraints |
|---|---|---|---|---|
| `code` | varchar(60) | no | — | Primary key, e.g. `academy.content.publish` |
| `label_ar`, `label_en` | varchar(120) | no | — | UI labels |
| `allowed_scopes` | varchar(60) | no | — | Comma-joined subset of `PLATFORM,COMPANY,DEPARTMENT,SELF` |
| `is_platform` | boolean | no | `false` | Platform permissions cannot be granted from a company |

Seeded from `docs/access-control.md` §2; a data test compares the table with the document list.
Rows are never deleted while a role or grant references them.

#### 2.0.6 `Role`
| Field | Type | Null | Default | Constraints / notes |
|---|---|---|---|---|
| `organization_id` | uuid FK → Organization | yes | `NULL` | `NULL` = system template (visible to all companies, immutable) |
| `key` | varchar(40) | no | — | `super_admin`, `company_admin`, …, `custom.<slug>` |
| `name_ar`, `name_en` | varchar(120) | no | — | |
| `is_system` | boolean | no | `false` | System roles cannot be edited/deleted |
| `description` | varchar(300) | yes | `NULL` | |

Constraints: `UNIQUE (organization_id, key)` with `NULLS NOT DISTINCT` (PostgreSQL 15+) so the
global key is unique; `CHECK (is_system = (organization_id IS NULL))`.
`Role.permissions` M2M → `Permission`. A company role may not include a `platform.*` permission.

#### 2.0.7 `RoleAssignment` (tenant)
| Field | Type | Null | Default | Constraints / notes |
|---|---|---|---|---|
| `membership_id` | uuid FK → Membership | no | — | Composite tenant FK |
| `role_id` | uuid FK → Role | no | — | Role must be global or same company (service + trigger) |
| `scope_type` | varchar(16) | no | — | `COMPANY \| DEPARTMENT \| SELF` (`PLATFORM` only on global platform assignments) |
| `scope_department_id` | uuid FK → Department | yes | `NULL` | Required iff `scope_type='DEPARTMENT'` |
| `granted_by_id` | uuid FK → Membership | yes | `NULL` | `SET NULL`; system seed may be null |
| `expires_at` | timestamptz | yes | `NULL` | Optional for temporary roles |

Constraints: `CHECK` scope arity; `UNIQUE (membership_id, role_id, scope_type, scope_department_id)
WHERE revoked_at IS NULL` via partial index with `COALESCE`; `revoked_at`, `revoked_by_id` for
history. Index `(organization_id, membership_id)`, `(organization_id, role_id)`.
`RoleAssignment` is tenant-only (`organization_id` is non-null). Platform authority lives in a
separate global table, `PlatformRoleAssignment(user_id, role_id, scope_type='PLATFORM',
granted_by_id, revoked_at)`, so no fake tenant organization is created and a company query can
never return a platform row. The last-platform-admin guard counts `PlatformRoleAssignment` rows.

#### 2.0.8 `PermissionGrant` (tenant, exceptional)
| Field | Type | Null | Default | Constraints |
|---|---|---|---|---|
| `membership_id` | uuid FK → Membership | no | — | |
| `permission_id` | varchar(60) FK → Permission | no | — | Platform permissions rejected |
| `scope_type` | varchar(16) | no | — | `COMPANY \| DEPARTMENT` |
| `scope_department_id` | uuid FK → Department | yes | `NULL` | |
| `reason` | varchar(500) | no | — | Non-blank, audited |
| `expires_at` | timestamptz | no | — | Required, ≤ 90 days, > now at creation |
| `granted_by_id` | uuid FK → Membership | yes | `NULL` | |
| `revoked_at`, `revoked_by_id` | timestamptz / uuid | yes | `NULL` | |

Constraints: partial `UNIQUE (membership_id, permission_id, scope_type, COALESCE(scope_department_id,'…')) WHERE revoked_at IS NULL`.
Index `(organization_id, expires_at) WHERE revoked_at IS NULL`.

#### 2.0.9 `Invitation` (tenant)
| Field | Type | Null | Default | Constraints |
|---|---|---|---|---|
| `email` | citext | no | — | Normalized; no account required yet |
| `token_hash` | char(64) | no | — | SHA-256 of a random 32-byte token; plaintext never stored |
| `expires_at` | timestamptz | no | — | 7 days |
| `accepted_at` | timestamptz | yes | `NULL` | |
| `invited_by_id` | uuid FK → Membership | yes | `NULL` | |
| `department_id` | uuid FK → Department | yes | `NULL` | |
| `roles` | M2M → Role | — | — | Must be company roles or `learner` |

Constraints: `UNIQUE (organization_id, email) WHERE accepted_at IS NULL` (one live invite),
`CHECK (expires_at > created_at)`, index `(token_hash)` unique. T-027 CP2 stores `roles` as the
jsonb list of company role codes (`employee`, `department_manager`) that the accepted membership
receives; the M2M `Role` relation arrives with the T-028 catalogue. Re-inviting deletes the
previous live row, and revoking deletes the row. Acceptance creates/reactivates
the `User` and `Membership` and applies active assignments. Acceptance **rejects an email that
already has a membership in another company**; for the same company it restores the removed row
instead of inserting a second one (`already_member` otherwise).

#### 2.0.10 `AccountToken` (global)
`user_id` FK, `purpose` (`verify_email|reset_password|unlock`), `token_hash` unique,
`expires_at`, `used_at`, `created_at`. Single use; previous unused token of the same purpose is
invalidated. Never logged.

#### 2.0.11 `MFADevice` / `RecoveryCode` (global)
`MFADevice`: `user_id`, `secret_encrypted` (Fernet/AES-GCM with `ACADEMY_MFA_ENCRYPTION_KEY`),
`confirmed_at`, `last_used_at`, `label`; unique active device per user.
`RecoveryCode`: `user_id`, `code_hash` (Argon2), `used_at`; 10 codes, regenerated as a set.

#### 2.0.12 `UserSession` (global)
`user_id`, `session_key_hash` unique, `created_at`, `last_seen_at`, `expires_at`,
`revoked_at`, `ip_prefix` (truncated, optional), `user_agent_family`. Listed/revoked by the
owner or a platform security admin; revoked on password change/reset and suspension.

#### 2.0.13 `PlatformRoleAssignment` (global)
`user_id` FK, `role_id` FK (global platform role), `granted_by_id` FK User nullable,
`revoked_at`, `revoked_by_id`, `expires_at`. Partial unique on active
`(user_id, role_id)`. Never mixed with tenant roles.

### 2.1 `Course` (tenant)
Container for versions. Adds real FKs to the new tenancy.

| Field | Type | Null | Default | Constraints / notes |
|---|---|---|---|---|
| `title` | varchar(200) | no | — | Non-blank |
| `description` | text | yes | `''` | |
| `owner_department_id` | uuid FK → Department | yes | `NULL` | D-013: `NULL` = general course (COMPANY scope to edit) |
| `status` | varchar(16) | no | `draft` | `draft \| published \| archived` |
| `created_by_id` | uuid FK → Membership | no | — | `PROTECT` |

Constraints: `CHECK (status IN ('draft','published','archived'))`,
`CHECK (length(btrim(title)) > 0)`. Composite FK `(organization_id, owner_department_id)`.
Indexes: `(organization_id, status)`, `(organization_id, owner_department_id)`.
The published version is **derived** from `CourseVersion` (§2.2); there is no
`Course.published_version` column (single source of truth).

### 2.2 `CourseVersion` (tenant)
An immutable snapshot once published.

| Field | Type | Null | Default | Constraints / notes |
|---|---|---|---|---|
| `course_id` | uuid FK → Course | no | — | Composite tenant FK, `PROTECT` |
| `version_number` | integer | no | — | ≥ 1, assigned by the clone service |
| `status` | varchar(16) | no | `draft` | `draft \| published \| archived` |
| `acknowledgment_required` | boolean | no | `false` | Learner must tick acknowledgment |
| `cover_media_id` | uuid FK → MediaAsset | yes | `NULL` | D-014, same company |
| `published_at` | timestamptz | yes | `NULL` | NOT NULL iff `status = 'published'` |
| `published_by_id` | uuid FK → Membership | yes | `NULL` | Same rule |
| `created_by_id` | uuid FK → Membership | no | — | |

Constraints:
- `UNIQUE (organization_id, course_id, version_number)`
- `UNIQUE (course_id) WHERE status = 'published'` — at most one published version per course.
- `CHECK (status <> 'published' OR (published_at IS NOT NULL AND published_by_id IS NOT NULL))`
- Immutability trigger `courseversion_immutable`: `UPDATE` of any column except
  `status`/`published_at`/`published_by_id` is rejected when the row is `published`; the only
  allowed status transition is `published → archived`.
Indexes: `(organization_id, course_id)`, partial `(organization_id) WHERE status = 'published'`.

### 2.3 `Section` (tenant)
| Field | Type | Null | Default | Constraints |
|---|---|---|---|---|
| `version_id` | uuid FK → CourseVersion | no | — | Composite tenant FK, `CASCADE` |
| `title` | varchar(200) | no | — | Non-blank |
| `position` | integer | no | — | ≥ 1 |

Constraints: `UNIQUE (version_id, position) DEFERRABLE INITIALLY DEFERRED`,
`CHECK (position >= 1)`. Child writes are rejected when the version is `published`
(trigger `version_content_frozen`).

### 2.4 `Lesson` (tenant)
| Field | Type | Null | Default | Constraints / notes |
|---|---|---|---|---|
| `section_id` | uuid FK → Section | no | — | Composite tenant FK, `CASCADE` |
| `title` | varchar(200) | no | — | Non-blank |
| `summary` | varchar(300) | yes | `NULL` | D-016 |
| `body` | text | yes | `''` | Text/PDF lesson body |
| `position` | integer | no | — | ≥ 1 |
| `content_type` | varchar(16) | no | `video` | `video \| text \| pdf` |
| `media_asset_id` | uuid FK → MediaAsset | yes | `NULL` | Required for `video` at publish time |
| `required` | boolean | no | `true` | Non-required lessons are skipped by the lock chain |
| `required_watch_percent` | smallint | no | `90` | `CHECK BETWEEN 50 AND 100` |

Constraints: `UNIQUE (section_id, position) DEFERRABLE INITIALLY DEFERRED`,
`CHECK (content_type IN ('video','text','pdf'))`, `CHECK (position >= 1)`,
`CHECK (content_type <> 'pdf' OR body IS NOT NULL)`; service validates video media readiness at
publish (§4).

### 2.5 `MediaAsset` (tenant)
| Field | Type | Null | Default | Constraints / notes |
|---|---|---|---|---|
| `kind` | varchar(16) | no | `video` | `video \| image \| document` |
| `status` | varchar(20) | no | `awaiting_upload` | State machine §5 |
| `storage_key` | varchar(512) | yes | `NULL` | `org/<organization_id>/media/<asset_id>/…`; never a URL |
| `original_filename` | varchar(255) | yes | `NULL` | Display only, sanitized |
| `content_type` | varchar(100) | yes | `NULL` | Trusted only after `stat` verification against an allowlist |
| `size_bytes` | bigint | yes | `NULL` | `CHECK (size_bytes IS NULL OR size_bytes >= 0)` |
| `checksum_sha256` | char(64) | yes | `NULL` | Lowercase hex |
| `duration_seconds` | numeric(10,3) | yes | `NULL` | From ffprobe; videos only |
| `renditions` | jsonb | no | `'{}'` | `{"360p": {...}, "720p": {...}}` written by the pipeline |
| `error_code` | varchar(40) | yes | `NULL` | e.g. `probe_failed`, `transcode_failed` |
| `attempt_count` | smallint | no | `0` | |
| `ready_at` | timestamptz | yes | `NULL` | |
| `created_by_id` | uuid FK → Membership | no | — | `PROTECT` |

Constraints: `CHECK (kind IN ('video','image','document'))`,
`CHECK (status <> 'ready' OR storage_key IS NOT NULL)`,
`CHECK (kind <> 'video' OR status <> 'ready' OR duration_seconds > 0)`,
`CHECK (status <> 'failed' OR error_code IS NOT NULL)`.
Indexes: `(organization_id, status)`, `(organization_id, created_at)`.

### 2.6 `Assignment` (tenant)
One target, one course.

| Field | Type | Null | Default | Constraints / notes |
|---|---|---|---|---|
| `course_id` | uuid FK → Course | no | — | Composite tenant FK, `PROTECT` |
| `target_type` | varchar(16) | no | — | `membership \| department \| role \| organization` |
| `target_membership_id` | uuid FK → Membership | yes | `NULL` | Required iff `membership` |
| `target_department_id` | uuid FK → Department | yes | `NULL` | Required iff `department` |
| `target_role_id` | uuid FK → Role | yes | `NULL` | Required iff `role`; role must be global or same company |
| `due_at` | timestamptz | yes | `NULL` | Stored UTC |
| `mandatory` | boolean | no | `true` | |
| `assigned_by_id` | uuid FK → Membership | yes | `NULL` | `SET NULL` for imported history |
| `note` | varchar(500) | yes | `NULL` | |
| `cancelled_at` | timestamptz | yes | `NULL` | Soft cancel; never delete |

Constraints:
- `CHECK` target arity: exactly one target column is set and it matches `target_type`;
  `organization` has none.
- Three partial unique indexes (one per concrete target) over
  `(organization_id, course_id, target_x) WHERE cancelled_at IS NULL`; one partial unique for
  `organization` on `(organization_id, course_id) WHERE target_type='organization' AND cancelled_at IS NULL`.
- `CHECK (cancelled_at IS NULL OR cancelled_at >= created_at)`.

Expansion (D-017): preview and write share one selector. `department` resolves through active
memberships in the department subtree, `role` through active role assignments of that company, a
`membership` to that one row, `organization` to every active membership. Memberships are active
only, de-duplicated, truncated at 5,000 with `capped = true`.

### 2.7 `Enrollment` (tenant)
Pins a member to one published version.

| Field | Type | Null | Default | Constraints / notes |
|---|---|---|---|---|
| `assignment_id` | uuid FK → Assignment | yes | `NULL` | `NULL` = direct/self enrollment |
| `course_id` | uuid FK → Course | no | — | Denormalized for reporting |
| `course_version_id` | uuid FK → CourseVersion | no | — | Pinned; never follows later publishes |
| `membership_id` | uuid FK → Membership | no | — | `PROTECT`; the learner in this company |
| `due_at` | timestamptz | yes | `NULL` | Copied from the assignment at creation |
| `mandatory` | boolean | no | `true` | Copied at creation |
| `status` | varchar(16) | no | `active` | `active \| completed \| cancelled` |
| `acknowledged_at` | timestamptz | yes | `NULL` | |
| `completed_at` | timestamptz | yes | `NULL` | |
| `cancelled_at` | timestamptz | yes | `NULL` | |
| `cancel_reason` | varchar(40) | yes | `NULL` | `unassigned \| deactivated \| removed_from_target` |

Constraints:
- `UNIQUE (organization_id, membership_id, course_id) WHERE status = 'active'`
- `CHECK (status <> 'completed' OR completed_at IS NOT NULL)`
- `CHECK (status <> 'cancelled' OR cancelled_at IS NOT NULL)`
- Re-enrollment inserts a **new** row: the partial index covers `active` only, and reactivation
  never revives a cancelled row (D-028).
- `member_changed` enrols a member into every live assignment that reaches them and cancels rows
  whose assignment no longer does (`removed_from_target`); `member_deactivated` cancels every
  active row (`deactivated`). Both run in the same transaction as the state change.
Indexes: `(organization_id, membership_id, status)`, `(organization_id, course_id, status)`,
`(organization_id, due_at) WHERE status = 'active' AND due_at IS NOT NULL`.

### 2.8 `LessonProgress` (tenant)
| Field | Type | Null | Default | Constraints / notes |
|---|---|---|---|---|
| `enrollment_id` | uuid FK → Enrollment | no | — | Composite tenant FK, `CASCADE` |
| `lesson_id` | uuid FK → Lesson | no | — | Composite tenant FK, `PROTECT` |
| `watched_ranges` | jsonb | no | `'[]'` | Ascending, disjoint `[[start, end], …]` seconds, 0.1 s precision |
| `watched_seconds` | numeric(10,1) | no | `0` | Derived cache of the ranges sum |
| `position_seconds` | numeric(10,1) | no | `0` | Last accepted position (server frontier source) |
| `frontier_seconds` | numeric(10,1) | no | `0` | Longest contiguous run from 0 |
| `last_heartbeat_at` | timestamptz | yes | `NULL` | Server clock only |
| `skip_attempts` | integer | no | `0` | Rejected forward jumps (abuse metric) |
| `completed_at` | timestamptz | yes | `NULL` | Set by the completion service, not by heartbeat |

Constraints: `UNIQUE (enrollment_id, lesson_id)`, `CHECK (watched_seconds >= 0)`,
`CHECK (position_seconds >= 0)`, `CHECK (frontier_seconds >= 0)`,
`CHECK (frontier_seconds <= position_seconds)`. The ranges invariant is enforced in the service;
the compaction task re-normalizes.

### 2.9 `CompletionRecord` (tenant)
Immutable proof of completion.

| Field | Type | Null | Default | Constraints |
|---|---|---|---|---|
| `enrollment_id` | uuid FK → Enrollment | no | — | `UNIQUE`, `PROTECT` |
| `course_id`, `course_version_id` | uuid | no | — | Snapshot for reporting |
| `membership_id` | uuid FK → Membership | no | — | Snapshot; `PROTECT` |
| `user_id` | uuid | no | — | Snapshot of the account UUID |
| `completed_at` | timestamptz | no | — | |
| `method` | varchar(16) | no | `lessons` | `lessons \| admin_override` |
| `actor_id` | uuid | no | — | Learner user id, or the admin for overrides |

Constraints: `UNIQUE (enrollment_id)`. Trigger rejects `UPDATE` and `DELETE`.

### 2.10 Quiz tables (Phase 1: schema only)
`Quiz` (`version_id`, `lesson_id` nullable, `title`, `pass_percent` 0–100, `max_attempts`),
`QuizQuestion` (`quiz_id`, `position`, `prompt`, `kind` = `single|multiple`),
`QuizChoice` (`question_id`, `position`, `label`, `is_correct`),
`QuizAttempt` (`quiz_id`, `enrollment_id`, `attempt_number`, `started_at`, `submitted_at`,
`score_percent`, `passed`), `QuizAttemptAnswer` (`attempt_id`, `question_id`, `choice_ids` jsonb,
`correct`). Each with tenant columns; `UNIQUE(quiz_id, enrollment_id, attempt_number)`.
**No Phase 1 endpoint writes these tables**; they exist so Phase 2 needs no destructive migration.

### 2.11 `ReminderLog` (tenant)
| Field | Type | Null | Default | Constraints |
|---|---|---|---|---|
| `enrollment_id` | uuid FK → Enrollment | no | — | |
| `kind` | varchar(24) | no | — | `due_minus_3 \| due \| due_plus_1 \| manager_escalation` |
| `recipient_membership_id` | uuid FK → Membership | no | — | Learner, or the manager for escalation |
| `recipient_role` | varchar(12) | no | `learner` | `learner \| manager` |
| `sent_at` | timestamptz | no | — | Server clock |

`UNIQUE (enrollment_id, kind, recipient_membership_id)` — the idempotency mechanism.
`UNIQUE (organization_id, id)` for composite references.

### 2.12 `NotificationLog` (tenant)
| Field | Type | Null | Default | Constraints |
|---|---|---|---|---|
| `kind` | varchar(32) | no | — | `course_assigned \| course_completed \| learner_completed \| manager_escalation \| account_*` |
| `dedupe_key` | varchar(128) | no | — | e.g. `completed:e-79` |
| `recipient_user_id` | uuid FK → User | no | — | Email resolved at send time |
| `recipient_membership_id` | uuid FK → Membership | yes | `NULL` | Null for account-level mail |
| `channel` | varchar(16) | no | `email` | `email \| in_app` |
| `status` | varchar(16) | no | `pending` | `pending \| sent \| failed \| skipped` |
| `attempt_count` | smallint | no | `0` | |
| `error_code` | varchar(40) | yes | `NULL` | |
| `sent_at` | timestamptz | yes | `NULL` | |

`UNIQUE (organization_id, dedupe_key, channel)`, `CHECK (status <> 'sent' OR sent_at IS NOT NULL)`.

### 2.13 `AuditEvent` (append-only, nullable tenant)
| Field | Type | Null | Default | Constraints |
|---|---|---|---|---|
| `event_id` | uuid | no | — | Idempotency |
| `organization_id` | uuid FK → Organization | yes | `NULL` | `NULL` = platform event |
| `actor_id` | uuid | no | — | User UUID snapshot; `system` events use the nil UUID + `actor_type='system'` |
| `actor_type` | varchar(10) | no | `user` | `user \| system` |
| `actor_membership_id` | uuid | yes | `NULL` | Snapshot, no FK |
| `action` | varchar(64) | no | — | Dotted, e.g. `role.updated`, `authorization.denied` |
| `object_type` | varchar(32) | no | — | |
| `object_id` | varchar(64) | no | — | UUID or code |
| `metadata` | jsonb | no | `'{}'` | IDs and non-secret before/after only |
| `request_id` | varchar(64) | yes | `NULL` | |
| `occurred_at` | timestamptz | no | — | Caller's transaction instant |

`UNIQUE (organization_id, event_id)` with `NULLS NOT DISTINCT`; indexes
`(organization_id, object_type, object_id)`, `(organization_id, occurred_at)`,
`(actor_id)`. `BEFORE UPDATE OR DELETE` trigger raises. Rows are written only through
`academy.audit.record`, which validates the action name and ids-only metadata and is idempotent
per `event_id`. Platform rows are readable only with `platform.audit.view`.

### 2.14 `AccessSuspension` (tenant, history)
| Field | Type | Null | Default | Constraints |
|---|---|---|---|---|
| `membership_id` | uuid FK → Membership | no | — | |
| `reason` | varchar(500) | no | — | Non-blank |
| `suspended_at` | timestamptz | no | — | `timezone.now()` |
| `suspended_by_id` | uuid FK → Membership | yes | `NULL` | |
| `lifted_at` | timestamptz | yes | `NULL` | Manual lift only |
| `lifted_by_id` | uuid FK → Membership | yes | `NULL` | Required iff lifted |

Constraints: partial `UNIQUE (membership_id) WHERE lifted_at IS NULL`,
`CHECK (lifted_at IS NULL OR lifted_by_id IS NOT NULL)`, `CHECK (length(btrim(reason)) > 0)`.
Enforcement is in the authorization layer: an active row yields no effective tenant capability
and the next request is denied with `403 access_suspended`; the learner sees X2. Roles and grants
are retained but ineffective. No local session store is tied to this table.

### 2.15 Hub webhook receipts (tenant, optional integration)
`academy_hubwebhookevent` — durable half of webhook idempotency (`docs/hub-contract.md` §4).
A delivery is accepted once per event id; a repeat with identical bytes is a duplicate, and the
same id with different bytes is a conflict.

| Field | Type | Null | Default | Constraints |
|---|---|---|---|---|
| `event_id` | uuid | no | — | `UNIQUE (organization_id, event_id)` |
| `event_type` | varchar(32) | no | — | `member_changed` or `member_deactivated` |
| `user_ref` | varchar(64) | no | — | Legacy Hub reference during migration |
| `body_sha256` | char(64) | no | — | Lowercase hex of the exact body |
| `received_at` | timestamptz | no | `timezone.now()` | |

The row is written in the same transaction as the event's effects, so a crash cannot
acknowledge an event whose effects rolled back.

### 2.16 Deliberately absent
| Not stored | Why |
|---|---|
| Per-heartbeat rows | Volume (14 req/s → 1.2 M rows/day) and privacy; merged ranges suffice (ADR-013) |
| Phone, address, birth date, photo, national ID | Not needed (D-037) |
| Precise IP, full user agent, device fingerprint | Privacy minimization; truncated prefix only for security, 90 d |
| Local Hub membership projection | Replaced: membership is now first-class (D-032) |
| Player session tokens | Playback uses short-lived presigned URLs; no Academy player token |
| Names/emails copied into business tables | Single source is `User`; reports join it under scope |

---

## 3. Relationships

```
Organization 1─n Membership 1─1 User  (H1.5: Membership.user_id is UNIQUE; platform-only users have 0 memberships)
Organization 1─n Department 1─n Department (parent)
Organization 1─n Role (custom) ; Role n─n Permission
Membership 1─n RoleAssignment n─1 Role
Membership 1─n PermissionGrant n─1 Permission
User 1─n PlatformRoleAssignment n─1 Role (global platform roles)
Organization 1─n Invitation n─n Role
User 1─n AccountToken / MFADevice / RecoveryCode / UserSession
Course 1─n CourseVersion 1─n Section 1─n Lesson
CourseVersion n─1 MediaAsset (cover) ; Lesson n─1 MediaAsset (video)
Course 1─n Assignment
Assignment 1─n Enrollment (0..n when a member joins the target later)
CourseVersion 1─n Enrollment (pinned) ; Membership 1─n Enrollment
Enrollment 1─n LessonProgress n─1 Lesson
Enrollment 1─1 CompletionRecord
Enrollment 1─n ReminderLog ; Organization/User 1─n NotificationLog
Quiz 1─n QuizQuestion 1─n QuizChoice ; Enrollment 1─n QuizAttempt 1─n QuizAttemptAnswer
Organization 0..1─n AuditEvent (platform events have no organization)
```

---

## 4. Invariants: who enforces what

| Invariant | Enforced by |
|---|---|
| Tenant isolation on every read | `for_org` (service/selector) + meta-test + composite FKs |
| No relation crosses companies | Composite foreign keys |
| One company membership per account (H1.5) | Table-level `UNIQUE (user_id)` (D-043) |
| No cross-company membership or second membership | Unique index + service + tests |
| One published version per course | Partial unique index |
| Published version content is frozen | Triggers on `CourseVersion`/`Section`/`Lesson` |
| Assignment target arity | `CHECK` + partial unique indexes |
| One active enrollment per member per course | Partial unique index |
| Completion requires every required lesson complete | Service (`complete_enrollment`) |
| Progress ranges are merged and disjoint | Service (`record_heartbeat`) |
| Completion and audit rows cannot change | Triggers |
| Side effects happen at most once | `NotificationLog`/`ReminderLog` unique keys + `dedupe_key` |
| Every video lesson has a `ready` asset before publish | Publish service (`publish_version`) |
| A version has ≥ 2 sections and ≥ 2 lessons | Publish service |
| Last platform/company admin cannot be removed | Role service, inside the transaction |
| Platform permissions never granted from a company | Catalogue `is_platform` + grant service |
| No self-escalation | Grant service (grantor must hold the permission at equal/broader scope) |

---

## 5. State machines

**Organization:** `active → suspended → active`, `active|suspended → archived` (no reverse).
Suspension blocks tenant access for every member; archive is read-only for the platform.

**User:** `unverified → active → suspended → active`, `active|suspended → deactivated`;
deactivation revokes sessions. Anonymization is a separate irreversible step after retention.

**Membership:** `invited → active → suspended → active`, `active|suspended → removed`. Removal
cancels unfinished enrollments; suspension does not. A removed membership is retained, and a
same-company restore (`removed → active`) may reuse that exact row before account anonymization;
it never revives cancelled enrollments. A second membership row, a cross-company re-invitation,
or moving an account between companies is rejected (D-043). `removed` is terminal for tenant
access unless the same-company restore is explicitly authorized and audited.

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

**Assignment:** `active → cancelled` only; cancelled rows are history.

**Enrollment:** `active → completed`, `active → cancelled`; `completed → active` is never
allowed (a re-assignment creates a new enrollment row after archival).

**PermissionGrant / RoleAssignment:** `active → revoked`; expiry is derived from `expires_at`
at read time, never written.

---

## 6. Video playback authorization

1. Learner calls `POST /api/v1/academy/enrollments/{id}/lessons/{lesson_id}/playback/`.
2. Service checks: enrollment membership = caller, tenant, lesson accessible (§7.5), asset `ready`.
3. Service presigns the variant playlist and rewrites segment/variant URIs with presigned URLs,
   TTL `max(30 min, 3 × duration)`, scoped to that asset's company prefix.
4. Response is `private, no-store`. URLs are never cached or logged.

---

## 7. Progress, gating and completion algorithm (normative)

This is the specification REQ-09 is tested against. Constants live in
`academy/progress.py` as module constants so tests can patch them.

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
{"from_seconds": 120.0, "to_seconds": 135.0, "playback_rate": 1.0}
```
Server clock only. Client timestamps, durations and ids are ignored.

### 7.3 Server algorithm
1. Lock the `LessonProgress` row (`SELECT … FOR UPDATE`) for the enrollment+lesson, creating it
   on first heartbeat. Reject if the lesson is not accessible (§7.5).
2. `elapsed = now - coalesce(last_heartbeat_at, now)` (0 on the first heartbeat).
   `credit_window = min(elapsed, MAX_HEARTBEAT_GAP_SECONDS)`.
3. `rate = clamp(playback_rate, MIN_PLAYBACK_RATE, MAX_PLAYBACK_RATE)`.
   If `playback_rate < MIN_PLAYBACK_RATE`, credit is 0.
4. `ceiling = position_seconds + credit_window * rate + SKIP_TOLERANCE_SECONDS`.
   On the first heartbeat, `position_seconds` is 0, so only ~2 s may be credited — the learner
   must earn coverage, never declare it.
5. **Skip check:** if `to_seconds > ceiling` → no state change except `skip_attempts += 1`, and
   respond **HTTP 400** `{"code": "progress_skip_rejected", "detail": …, "fields":
   {"allowed_seconds": ceiling}}`. The counter is committed and `last_heartbeat_at` is left
   alone, so waiting and retrying is credited normally.
6. **Rewind** (`to_seconds <= position_seconds`): credit nothing and update `last_heartbeat_at`.
   On the first heartbeat nothing is credited at all (`credit_window` is 0, tolerance only widens
   the ceiling). `frontier_seconds <= position_seconds` keeps the high-water mark.
7. **Forward within ceiling:** credit `[max(from_seconds, position_seconds), to_seconds]`, never
   more than `credit_window * rate`. If `from_seconds < position_seconds -
   RANGE_MERGE_GAP_SECONDS`, the gap is not credited.
8. Merge the credited interval into `watched_ranges`: sort by start; merge when
   `next.start - current.end <= RANGE_MERGE_GAP_SECONDS`; clamp to `[0, duration_seconds]`;
   round to 0.1 s. Recompute `watched_seconds` and `frontier_seconds`.
9. `position_seconds = to_seconds`, `last_heartbeat_at = now`. Commit.
10. Respond `200` with `{"position_seconds", "watched_seconds", "frontier_seconds",
    "coverage_percent", "skippable_seconds"}`. `coverage_percent = watched_seconds /
    duration_seconds × 100` (0 when duration is 0).

### 7.4 Idempotency and concurrency
- Replaying an identical heartbeat credits 0 and never corrupts state — merging is monotone.
- One writer per row: the row lock serializes concurrent heartbeats; the second sees the updated
  position and its ceiling. No lost updates, no double credit.
- Heartbeats are **not** audited (volume) and **not** stored individually (ADR-013).

### 7.5 Sequential gating
`lesson_accessible(enrollment, lesson)`:
1. The lesson belongs to `enrollment.course_version` (otherwise 404).
2. Every **required** lesson earlier in reading order (`section.position`, then
   `lesson.position`) in the same version has `completed_at IS NOT NULL`.
3. Non-required lessons are skipped by the chain; they can be opened at any time but do not gate
   later lessons.

Violating (2) returns **403** `{"code": "lesson_locked"}` with `fields.{"next_lesson_id"}`
pointing at the blocking lesson. The API never returns lesson content for a locked lesson, so the
lock is not a UI-only affordance.

### 7.6 Lesson completion
`POST /enrollments/{id}/lessons/{lesson_id}/complete/` (explicit, learner-initiated):
- Requires `watched_seconds / duration_seconds × 100 >= required_watch_percent`;
  `duration_seconds` is the lesson's own media asset duration.
- `duration_seconds` of 0 (text/pdf lessons) completes on explicit confirmation.
- Idempotent: a second call returns the same completion with `200`.
- Not eligible → **409** `{"code": "lesson_not_eligible"}` with
  `fields.{"coverage_percent", "required_percent"}`.
- Sets `LessonProgress.completed_at`, emits `lesson_completed` on commit.

### 7.7 Enrollment completion
Requires every required lesson of the pinned version completed, **and** acknowledgment recorded
when `CourseVersion.acknowledgment_required`. Then, in one transaction:
`Enrollment.status='completed'`, `completed_at=now`, insert `CompletionRecord` (unique on
enrollment makes a double submit a no-op), emit `enrollment_completed` on commit. Response is
`200`, never `201`.

### 7.8 Reminder and escalation evaluation
Hourly beat task evaluates companies whose **local** time is `reminder_hour` (D-038), then:
- `due_minus_3`, `due`, `due_plus_1` for active enrollments with `due_at` on that local day,
  skipping completed/cancelled; each insert into `ReminderLog` is the idempotency gate.
- `manager_escalation` at `due + 3 days`: one digest per manager per day. Manager resolution:
  `Assignment.assigned_by_id` when present, otherwise active memberships holding the
  `training_manager` role for the learner's department; if none, the Company Admin. Never more
  than one digest per recipient per day.
- Re-running on the same day writes nothing (unique keys), including across a DST change because
  the idempotency key is the local date, not the hour.

### 7.9 Accepted residual risk
A forged client can claim up to `credit_window × rate` per heartbeat, so it must sustain
heartbeats to accumulate coverage. Mitigations: server-side merged ranges, `skip_attempts`, and
reports exposing completion time versus assignment time. Documented rather than solved because no
browser-side signal is trustworthy (CHARTER risk table).

---

## 8. Retention and privacy per table

| Table | Retention | Privacy handling |
|---|---|---|
| `User` | Account life + 90 d after last membership removal | Anonymize email/name; keep UUID for history |
| `Membership` | Life + 5 y (training evidence) | Department/state only; no email |
| `Invitation` | 30 d after expiry/acceptance | Email deleted with the row |
| `AccountToken`, `UserSession` | Tokens 24 h / sessions 30 d | Hashed; purged by jobs |
| `MFADevice`, `RecoveryCode` | Until removed/used | Encrypted secret / Argon2 hashes |
| `CompletionRecord`, `AuditEvent` | 5 y | Export/anonymize by user UUID |
| `LessonProgress` | Life of enrollment; ranges compacted after 12 mo | Learner behavior data |
| `NotificationLog`, `ReminderLog` | 90 d | User/membership ids only |
| `MediaAsset` stale uploads | 24 h | Storage object deleted with the row |
| `Enrollment` | Life + retention period | Keeps membership FK; anonymization is on `User` |
| `AccessSuspension` | 5 y with audit | Reason may contain personal context; export covers it |

The meta-test in `academy/tests/test_privacy.py` fails when a model with account-level PII or a
`user_ref`-like column is missing from the export/anonymize registry (REQ-19).

---

## 9. Index, integrity and performance obligations
- Tenant indexes lead with `organization_id`; a data test lists every tenant index and fails on a
  leading column that is not `organization_id` or a unique key.
- No index is added “just in case”: each new index names the query/report it serves in the PR.
- Composite FKs require `UNIQUE (organization_id, id)` on parents; the migration adds these
  constraints before the FKs.
- `EXPLAIN (ANALYZE, BUFFERS)` evidence is recorded for: enrollment list, report aggregation,
  due-reminder scan, audit search, media stale purge.
- Partitioning is not implemented. Revisit trigger: > 50 M rows in `AuditEvent` /
  `LessonProgress`, or p95 degradation attributable to them (D-041).
- RLS is not enabled; isolation evidence is the G7 architecture/isolation suite plus composite
  FKs (D-041).

## 10. Test obligations produced by this document
- `test_progress_skip_matrix`: forward jump rejected; rewind credits nothing; paused gap does not
  credit beyond `MAX_HEARTBEAT_GAP_SECONDS`; rate 3.0 credits at 2.0; duplicate heartbeat is a
  no-op.
- `test_gating_matrix`: locked lesson returns 403 and no body; non-required lessons skipped.
- `test_completion_idempotency`: double submit yields one `CompletionRecord` and one
  notification key.
- `test_access_suspension`: a suspended membership has no effective capability, keeps every
  stored role/grant, and a lift restores exactly those.
- `test_tenancy_constraints`: every composite FK rejects a cross-company parent; the isolation
  suite covers every entity with a two-company fixture.
- `test_identity_lifecycle`: invitation → active; removal keeps history; anonymization keeps the
  UUID and clears PII; email is unique and changeable.
- `test_role_matrix`: the catalogue matches `docs/access-control.md` §2 and every default role's
  permission set matches §3.
- Constraint tests: every `CHECK`/unique index above has one `IntegrityError` test.
