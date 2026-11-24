# Academy wireframes

Previous baseline (1.png / 2.jpeg) superseded by the PDF.

The source is the owner's `docs/ui/reference/masheed-academy-screens.pdf`. The [approved Masheed page renders](reference/pages/) are tracked. Pages 1–2 inform brand mood. Page 3 informs placement in Masheed Hub. Functional requirements come from CHARTER and ARCHITECTURE.

## Visual language

Values sampled from flat pixels in the Poppler renders. The color roles below remain usable in any frontend. Implementations use the shared token file and darker semantic foregrounds for text contrast.

| Role | Sample | PDF page | Archived cross-check |
|---|---|---|---|
| Brand gold | `#E8AA23` | 5, 11, 21, 22 | Exact `#E8AA23` |
| Sidebar and primary actions | `#101820` | 5, 11, 22 | Near `#101920` |
| Active navigation row | `#282F36` | 5, 22 | PDF value replaces `#2F333C` |
| Canvas | `#F8FAFC` | 5, 11, 16, 21, 22 | Near `#F9FAFC` |
| White cards | `#FFFFFF` | 5, 11, 16, 17, 22 | Exact `#FFFFFF` |
| Hairline border | `#E2E8F0` | 5, 16, 21, 22 | PDF cool gray replaces `#ECECEC` |
| Success/progress | `#10B981` / `#ECFDF5` | 5, 21, 22 | PDF samples |
| Overdue background | `#FEF2F2` | 22 | PDF sample |
| In-progress background | `#FFFBEB` | 22 | PDF sample |
| Draft/neutral background | `#F1F5F9` | 5, 11, 22 | PDF sample |
| Player | `#0B1117` | 21 | PDF sample |

Rounded panels use a 12 px radius, a thin border, and a regular 4 px spacing scale. The dark theme derives from the sampled navy with lighter foregrounds. Noto Sans Arabic is hosted locally under the D-008 branding default. The archived color values were used only for the cross-check column.

## A–F reference wireframes (A is course management, not the personal dashboard)

Each row describes the reading order and panel placement. RTL reverses inline placement. On phones the sidebar uses a drawer and table rows read as labeled cards.

| Screen | PDF | Wider layout | Phone reading order and states |
|---|---|---|---|
| A · Academy | [5](reference/pages/page-05.png) | Sidebar / breadcrumb + heading + new course / tabs / filters / course table | Heading/actions → tabs → filters → course cards. Draft, published and archived tags describe status in text. |
| B · New course | [11](reference/pages/page-11.png) | Breadcrumb + title / two editor steps / title and description / owner and cover side by side / acknowledgment toggle / actions | Same reading order with stacked fields. Keep the save and next actions visible after the toggle. |
| C · Lessons and upload | [16](reference/pages/page-16.png) | Editor steps / ordered lesson rows / actions / add-lesson dialog design with file, progress and error state | Rows reflow and the dialog fields stack. Use the configured upload policy and section ordering from ARCHITECTURE. |
| D · Assignment | [17](reference/pages/page-17.png) | Dimmed course backdrop / centered dialog with target, department, due date, requirement, recipient preview and actions | One column. Employee, department and role are shown. Recipient count is sample data. |
| E · Course player | [21](reference/pages/page-21.png) | Header + course progress / outline and acknowledgment beside the player / resume and next controls | Video first, then outline, acknowledgment and completion. Disabled and enabled states have visible explanations. |
| F · Team training | [22](reference/pages/page-22.png) | Sidebar / header + export / three metrics / filters / training table | Metrics then filters and labeled cards. Overdue and completed states have visible text. |

The component showcase includes acknowledgment hidden, disabled, available and checked, plus completion disabled, enabled, submitting and done. The planned course action rules are recorded in `docs/domain-model.md` §5 (state machines) and `docs/api.md` §4 (course/version actions). The [HTML email](emails/escalation-digest.html) and [text email](emails/escalation-digest.txt) are presentation artifacts.

## G. Permissions

Show the **Permissions** tab in Academy management only to users with effective `academy.admin`. Use the T-013 shell, responsive table and status styles from [pages 5 and 22](reference/pages/), and the [page 17 dialog pattern](reference/pages/page-17.png).

| Area | Wide layout | Phone and tablet |
|---|---|---|
| Entry and actions | Management tabs → Permissions heading → **Grant access** | Same reading order. Keep the main action visible above the user list. |
| Users and access | User, capability, department scope, source, expiry, and status in a table. In H1 `grants_only`, show individual Academy grants as the effective source; Hub roles may be shown as identity metadata but **never** as automatic training-management authority. | User rows become labeled cards on phones. Keep capability, scope, expiry and action together. |
| Grant dialog | Choose one user and capability. Select all departments or choose allowed departments. Add an optional expiry date and submit. | Stack fields and show validation next to the field. Scoped admins only see departments they can administer. |
| Revoke | A **Revoke** action appears for individual grants the viewer can administer. The confirmation shows the user, capability and scope. | Reuse the same confirmation. Keep revoked history visible and label active, expired and revoked states in text. If revocation would remove the last active admin, show the reason. |

The layout mirrors for Arabic RTL and supports English LTR, keyboard operation, and the T-013 phone, tablet and desktop widths. T-016 provides a development-only example with synthetic user rows, scope selection, sample validation, a revoke confirmation, and a protected last-admin row. The production tab and permission writes are represented by this wireframe and protected by the server-side checks in ARCHITECTURE §7 when connected to the production interface.

## Model gaps

| Visual item | Current schema or contract | Decision |
|---|---|---|
| Course owner department and the “general” option | `Course.owner_department_ref` (nullable; `NULL` = general course) — `docs/domain-model.md` §2.1 | D-013 (resolved) |
| Cover image | `CourseVersion.cover_media` (nullable FK) and `MediaAsset.kind = 'image'` — see `docs/domain-model.md` §2.2 | D-014 (resolved) |
| Assignment target “everyone” | `Assignment.target_type` includes `organization` — `docs/domain-model.md` §2.6 | D-015 (resolved) |
| Short lesson summary | `Lesson.summary` (300 chars) — `docs/domain-model.md` §2.4 | D-016 (resolved) |
| Recipient-count preview | `POST /manage/assignments/preview/` returns a count only — `docs/api.md` §5 | D-017 (resolved) |

## Preview routes

In development, open `/academy/preview/`. T-013 ships the shell, the design tokens, the component
patterns and the sample states at `/academy/preview/ar/` and `/academy/preview/en/`; the A–G,
L1–L4 and S1 screens arrive with the tasks that implement them. Use the menu and language switch
to move between the sections and the two reading directions. Screen G is at `/academy/preview/ar/permissions/` and `/academy/preview/en/permissions/`. Append `?state=loading`, `?state=empty`, `?state=error`, `?state=forbidden`, or `?state=slow` to see the corresponding sample. Use `?dialog=grant&state=validation` for the field error. The grant and revoke dialogs also have links for browsing without JavaScript. Preview actions use sample data and write nothing.

## Account screens

Both account screens use the shared canvas and card in Arabic (RTL) and English (LTR). The development sign-in stacks a title, labeled username and password fields, any validation messages, and the sign-in button. The inactive-account screen stacks its title, a short message directing members to their organization administrator, and the sign-out button.


## H1 screen additions and navigation

The owner-approved H1 UX target is described in
[`screen-specification.md`](screen-specification.md). These additions **do not
rename or replace** the PDF reference screens A–G:

- **L1 Personal Dashboard:** assignments, active learning, progress and resume.
- **L2 My Courses:** own courses, status and due dates.
- **L3 Course Details:** summary, ordered lessons, locked/unlocked states.
- **L4 Achievements:** completed courses and dates, without Phase 1 certificates.
- **S1 Audit:** scoped read-only audit table for authorized `academy.admin`.
- **X1 Local Sign-in:** standalone mode only; Hub entry has no Academy login.

**Academy sidebar:** My Learning (Dashboard, My Courses, Achievements);
Training Management (Courses & Content, Assignments, Reports); System Management
(Permissions, Audit). Each management link is individually permission-gated,
and a section is hidden when it has no visible child links. A contextual
Return to Hub link is optional only in integrated mode. Server-side checks
remain mandatory. On phones the sidebar becomes an accessible drawer.

**Design source:** continue to use the approved PDF's navy, gold, white cards,
RTL/LTR patterns and responsive layouts. The new screen specification defines
content, behavior and states; it does **not** claim new screen mockups have
been approved or built.
