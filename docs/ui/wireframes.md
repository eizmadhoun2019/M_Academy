# Academy wireframes

**Status:** interim functional reference, 2026-11-25. The final visual package has **not** been
delivered and no final design is claimed as approved (D-044).

Previous baseline (1.png / 2.jpeg) is superseded by the owner's
`docs/ui/reference/masheed-academy-screens.pdf`; the [tracked page renders](reference/pages/) are
interim. Pages 1–2 inform brand mood. Page 3 informs Hub placement. Functional requirements come
from CHARTER and ARCHITECTURE. Mobile first and the visual-reference gate are in
`screen-specification.md` §6–§7.

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

Rounded panels use a 12 px radius, a thin border, and a regular 4 px spacing scale. The dark theme derives from the sampled navy with lighter foregrounds. **Rubik** (Arabic + Latin, hosted locally) is the approved brand font (D-008/D-044). The sampled values are an interim token basis, not the final design system; the final package supplies the complete tokens. The archived color values are cross-checks only.

## A–F interim wireframes (A is course management, not the personal dashboard)

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

## G → N2. Roles and grants (formerly “Permissions”)

The old single tab is replaced by the company administration screen **N2 — Roles & grants**,
visible only with `academy.role.manage` or `academy.grant.manage`. It uses the T-013 shell,
responsive table and status styles from [pages 5 and 22](reference/pages/), and the
[page 17 dialog pattern](reference/pages/page-17.png).

| Area | Wide layout | Phone and tablet |
|---|---|---|
| Entry and actions | Administration → **Roles & grants** → tabs **Members**, **Roles**, **Grants** → primary action per tab | Same reading order; primary action remains above the list |
| Members | Member, department(s), roles, effective scope, state, last change | Rows become labelled cards; role/scope/action stay together |
| Roles | System roles (read-only description) and custom company roles; permission count; members count | Stacked cards; “view permissions” opens a drawer |
| Grants | Member, permission, scope, reason, expiry, state (`active`, `expired`, `revoked`), grantor | Same fields in a card; revoke in the card menu |
| Grant dialog | Member → permission (filtered to what the actor may delegate) → scope (company/departments) → expiry → reason → confirm | Stacked fields, inline validation; platform permissions never offered |
| Revoke | Confirmation names member, permission and scope; optional reason; history retained | Same confirmation; disabled with a reason if it would remove the last admin |

Scoped admins only see departments they can administer. The UI mirrors for Arabic RTL, supports
English LTR and keyboard operation at the three widths. The current T-016 preview remains sample
data only; production writes are defined by `docs/api.md` and enforced server-side.

## Design-gate record (D-044)

The final package is delivered per screen group, not assumed from the interim PDF. A group may be
implemented only when this table records an owner approval date + package version, or an explicit
owner waiver. A waiver does not claim pixel compliance; visual regression still runs where a
reference exists.

| Group | Interim basis | Final reference |
|---|---|---|
| P1–P5 public | token system + public layout | **not delivered — gate pending** |
| X1–X6 auth | account pattern from PDF | **not delivered — gate pending** |
| Shell + L1–L4/E | PDF card/player language | **not delivered — gate pending** |
| A–D/F training management | PDF pages 5/11/16/17/21/22 | **interim only — final package pending** |
| N1–N4/S1 company admin | PDF table/dialog patterns | **not delivered — gate pending** |
| N5–N8/S2 platform admin | PDF table/dialog patterns | **not delivered — gate pending** |

Required at approval: Screen Designs, Design Tokens, Typography, Colors, Spacing, Components,
Responsive Layouts (320/390/768/1440), Interaction States, Accessibility Requirements and Visual
Acceptance Criteria. Images alone are not an engineering specification.

## Model gaps

| Visual item | Current schema or contract | Decision |
|---|---|---|
| Course owner department and the “general” option | `Course.owner_department_id` (nullable; `NULL` = general course) — `docs/domain-model.md` §2.1 | D-013 (resolved) |
| Cover image | `CourseVersion.cover_media` (nullable FK) and `MediaAsset.kind = 'image'` — see `docs/domain-model.md` §2.2 | D-014 (resolved) |
| Assignment target “everyone” | `Assignment.target_type` includes `company` — `docs/domain-model.md` §2.6 | D-015 (resolved) |
| Short lesson summary | `Lesson.summary` (300 chars) — `docs/domain-model.md` §2.4 | D-016 (resolved) |
| Recipient-count preview | `POST /manage/assignments/preview/` returns a count only — `docs/api.md` §5 | D-017 (resolved) |

## Preview routes

In development, open `/academy/preview/`. T-013 ships the shell, the design tokens, the component
patterns and the sample states at `/academy/preview/ar/` and `/academy/preview/en/`; the A–G,
L1–L4 and S1 screens arrive with the tasks that implement them. Use the menu and language switch
to move between the sections and the two reading directions. Screen G is at `/academy/preview/ar/permissions/` and `/academy/preview/en/permissions/`. Append `?state=loading`, `?state=empty`, `?state=error`, `?state=forbidden`, or `?state=slow` to see the corresponding sample. Use `?dialog=grant&state=validation` for the field error. The grant and revoke dialogs also have links for browsing without JavaScript. Preview actions use sample data and write nothing.

## Account screens

Both account screens use the shared canvas and card in Arabic (RTL) and English (LTR). The development sign-in stacks a title, labeled username and password fields, any validation messages, and the sign-in button. The inactive-account screen stacks its title, a short message directing members to their organization administrator, and the sign-out button.


## H1.5 screen additions and navigation

The owner-approved target is [`screen-specification.md`](screen-specification.md). It **does not
rename or replace** the PDF reference screens A–G; it adds public, auth, learner, administration
and platform screens.

- **P1–P5 Public:** home, about, programmes, contact, privacy/terms on `/`, no session.
- **X1–X6 Auth:** login, forgot/reset, verify, accept invitation, access denied. There is no
  company-selection screen.
- **L1–L4 + E Learner:** dashboard, my courses, course details, achievements, player.
- **N1–N4 + S1 Company administration:** members, roles & grants, departments, settings, audit.
- **N5–N8 + S2 Platform administration:** overview, companies, platform users, platform settings,
  platform audit.
- **A–F Training management:** the PDF screens, now company-scoped and permission-gated.

**Sidebar groups:** My Learning (Dashboard, My Courses, Achievements); Training Management
(Courses & Content, Assignments, Reports); Company Administration (Members, Departments, Roles &
Grants, Settings, Audit); Platform Administration (Overview, Companies, Platform Users, Platform
Settings, Audit). A group is hidden when it has no visible child, every item is permission-gated,
and server checks remain mandatory. On phones the sidebar is an accessible drawer. The public
header uses simple links and a Sign in button; there is no application sidebar.

**Design source:** the interim PDF's navy, gold and white-card language plus the approved identity
(Primary `#101820`, Gold `#E8AA23`, Rubik, official logo and geometric element). Every screen is
designed Mobile 390 → Tablet 768 → Desktop 1440 and tested from 320 px. The new specification
defines content, behavior and states; it does **not** claim new mockups are approved or built.
Preview routes under `/academy/preview/` are sample data and are extended by T-029/T-030.

## Screen-by-screen wireframe coverage
| Screen | Wireframe source | Status |
|---|---|---|
| A–F | PDF pages 5, 11, 16, 17, 21, 22 | interim reference; final package pending |
| N2 (was G) | PDF page 5/17 patterns, above | specified |
| L1–L4, E | PDF cards/player language | specified; no pixel mockup |
| P1–P5 | token system, public layout | specified; no pixel mockup |
| X1–X6 | existing account screen pattern | specified; X1/X6 implemented in T-013/T-014; final reference pending |
| N1, N3–N8, S1–S2 | PDF table/dialog patterns | specified; final reference pending |

## Model gaps

| Visual item | Current schema or contract | Decision |
|---|---|---|
| Course owner department and the “general” option | `Course.owner_department_id` (nullable; `NULL` = general course) — `docs/domain-model.md` §2.1 | D-013 (resolved) |
| Cover image | `CourseVersion.cover_media` (nullable FK) and `MediaAsset.kind = 'image'` — `docs/domain-model.md` §2.2 | D-014 (resolved) |
| Assignment target “everyone” | `Assignment.target_type` includes `company` — `docs/domain-model.md` §2.6 | D-015 (resolved) |
| Short lesson summary | `Lesson.summary` (300 chars) — `docs/domain-model.md` §2.4 | D-016 (resolved) |
| Recipient-count preview | `POST /manage/assignments/preview/` returns a count only — `docs/api.md` §5 | D-017 (resolved) |
