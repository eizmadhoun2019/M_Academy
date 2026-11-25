# REPORTS — Metric Definitions, Columns and CSV Format

**Status:** Canonical for REQ-12. `docs/api.md` §7 owns the routes; this file owns what each
response contains and how every number is computed.
**Last updated:** 2026-11-25
**Consumed by:** T-022 (company reports), T-032 (tenant-aware adaptation), T-030/T-031 (UI).

---

## 1. Definitions (one meaning each, used everywhere)
All metrics are computed **inside one company** unless the endpoint is explicitly a platform
endpoint (§7). A query never aggregates two companies into one row.

| Term | Definition |
|---|---|
| **Eligible enrollment** | An `Enrollment` with `status IN ('active','completed')` inside the report scope. Cancelled enrollments are never counted. |
| **Completed** | `status='completed'` (a `CompletionRecord` exists). |
| **In progress** | `status='active'` and at least one `LessonProgress` row with `watched_seconds > 0`. |
| **Not started** | `status='active'` with no watched progress. |
| **Overdue** | `status='active'` and `due_at IS NOT NULL` and `due_at < now()`. A learner at exactly `due_at` is not yet overdue. |
| **Completion %** | `completed / eligible × 100`, rounded to one decimal, `0.0` when the denominator is 0 (never blank, never an error). |
| **Average completion time** | Mean of `completed_at − created_at` over the *completed* rows of the same filtered result set (the window applies to `created_at`), in days with one decimal; `null` when that set holds no completed row. |
| **Days overdue** | `floor((now() − due_at) / 1 day)`, minimum 0. |
| **Last activity** | `MAX(LessonProgress.last_heartbeat_at)` for the enrollment. |
| **Progress %** | Completed lessons ÷ lessons in the pinned version × 100, one decimal. Archived versions are counted as they were. |
| **Filter window** | `from`/`to` apply to the date named by the endpoint (completion rows: `completed_at`; overdue rows: `due_at`; summary: the enrollment's `created_at`). Absent bounds mean all time. `from > to` → `400 invalid_range`. Dates are interpreted in the company time zone. |
| **Company scope** | Every row belongs to the active company. A platform user must select a company or use the platform endpoint; there is no implicit “all companies merged” company report. |

## 2. `GET /manage/reports/summary/`
Query: `group_by=course|department` (default `course`), `course`, `department`, `from`, `to`.
Response: `{"rows": [...], "totals": {...}, "generated_at": "..."}`.

| Column | Type | Notes |
|---|---|---|
| `group_key` | string | Course UUID or department UUID |
| `group_label` | string | Local display name (`Course.title` / `Department.name`); general courses use the company's `general_courses_label` setting. Falls back to the key only if the name is empty. No Hub lookup. |
| `eligible` | int | |
| `completed` | int | |
| `in_progress` | int | |
| `not_started` | int | `eligible − completed − in_progress` |
| `overdue` | int | |
| `completion_percent` | decimal(4,1) | §1 |
| `average_completion_days` | decimal(6,1) \| null | `null` when nothing completed in the window |
| `mandatory_eligible` | int | Mandatory-only subset, for the dashboard's compliance view |

`totals` repeats every numeric column over all rows; `completion_percent` there is computed from
the summed counts, not averaged across rows.

## 3. `GET /manage/reports/overdue/`
Query: `course`, `department`, `min_days_overdue`, `page`/`page_size` (default 25, max 100).
Sorted by `days_overdue` desc, then `due_at` asc. Response: `{"count", "results", …}`.

| Column | Type | Notes |
|---|---|---|
| `enrollment_id` | uuid | Stable link target |
| `user_id` | uuid | Learner account id; never an email in the report payload |
| `display_name` | string | From `User.display_name`; empty string when the account has no name yet |
| `course_title` | string | From the pinned version |
| `due_at` | ISO-8601 UTC | |
| `days_overdue` | int | §1 |
| `progress_percent` | decimal(4,1) | §1 |
| `last_activity_at` | ISO-8601 \| null | `null` = never opened |
| `mandatory` | bool | |

## 4. `GET /manage/reports/completion/`
Per-learner rows. Query: `course`, `department`, `status=active|completed|overdue|all`
(default `all`), `from`, `to`, cursor or page. Response: `{"next", "results", …}` with
`ACADEMY_CURSOR_PAGE_SIZE` rows when a cursor is supplied.

| Column | Type | Notes |
|---|---|---|
| `enrollment_id`, `user_id`, `display_name`, `course_title` | uuid / uuid / string / string | |
| `version_number` | int | The pinned version, not the current one |
| `status` | string | `active \| completed \| cancelled` (cancelled only with `status=all`) |
| `progress_percent` | decimal(4,1) | |
| `completed_at` | ISO-8601 \| null | |
| `method` | string \| null | `lessons \| admin_override` |
| `due_at` | ISO-8601 \| null | |
| `days_overdue` | int | `0` when not overdue |

## 5. `GET /manage/reports/export.csv`
Same filters as §4 except pagination, plus `columns` (comma-separated allowlist; default all).
Streamed, not buffered; no row cap because the query is bounded and indexed.

Format rules:
- `Content-Type: text/csv; charset=utf-8`, `Content-Disposition: attachment; filename="academy-completion-<from>-<to>.csv"` (the literal `all` stands in for an absent bound), `Cache-Control: private, no-store`.
- Encoding `utf-8-sig` (BOM) so Arabic opens correctly in Excel; line endings CRLF.
- Header row is the snake_case column names of §4, in the order requested.
- Values: timestamps ISO-8601 UTC; decimals with `.` as separator regardless of locale;
  booleans `true`/`false`; empty cell for `null` (never `None` or `null`).
- Formula injection: any cell beginning with `= + - @`, tab or carriage return is prefixed
  with `'`. Applied after formatting, before writing.
- Each export writes one `AuditEvent` (`report.exported`) with the filter set (no learner
  identifiers, no email), throttled at 5/hour per user and company.

## 6. Scope, performance and tests
- `academy.report.view` with **COMPANY** scope sees the active company; **DEPARTMENT(S)** scope sees only
  enrollments whose course `owner_department_id` is in the granted set, plus courses with
  `owner_department_id IS NULL` (general courses). A manager never sees a department they cannot
  administer. Cross-company ids return 404/403 before any query runs.
- Query budget: the summary endpoint runs a fixed number of queries regardless of row count
  (asserted with `django_assert_num_queries`); completion rows use `select_related` and
  `values()` so an N+1 fails the suite.
- p95 target for all four endpoints: < 300 ms at design capacity (`docs/performance-profile.yaml`).
- Tests: two companies and three departments covering completed, in-progress, not-started,
  overdue and cancelled, asserting every column of §2–§5; a formula-injection fixture (`=1+1`,
  `@SUM`, `-2+3`, tab-leading) asserting the prefix; a BOM assertion on the raw CSV bytes;
  a department-scope denial test (`403 forbidden`); a company-isolation test proving company B's
  rows never appear in company A's totals; a company-time-zone assertion for `from`/`to` and
  `due_at` rendering.

## 7. Platform summary — `GET /platform/reports/summary/`
Read-only, permission `platform.organization.view` (`docs/access-control.md` §2), with an
**explicit `organization` filter** (single company) or `group_by=organization` (one row per
company). There is no unscoped “all data in one row” mode.

| Column | Type | Notes |
|---|---|---|
| `organization_id`, `organization_name` | uuid / string | |
| `active_members`, `active_courses` | int | Current state |
| `eligible`, `completed`, `overdue` | int | §1, within that company |
| `completion_percent` | decimal(4,1) | §1 |
| `last_activity_at` | ISO-8601 \| null | Latest heartbeat in that company |

The platform endpoint never returns learner-level rows; drilling into a company uses the company
endpoints under an explicit platform-access grant and is audited (D-034). Its p95 target is
< 500 ms for 10 companies; it may run one aggregate query per company, but the count is fixed by
the number of selected companies and must be asserted.
