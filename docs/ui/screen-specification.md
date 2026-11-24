# Masheed Academy — H1 Screen Specification

> **Status:** Adopted 2026-11-23 (owner-directed; charter 2.3). It specifies the **target**,
> not verified implementation.
> **Scope:** Masheed organization only; one shared training experience in Hub-integrated
> and production standalone modes. This file specifies desired UI, not verified code.
> **Visual source:** `docs/ui/reference/masheed-academy-screens.pdf` (23 pages);
> existing A–G mappings in `docs/ui/wireframes.md` are preserved.
> **Authority:** CHARTER > RULES > ARCHITECTURE. Adoption is recorded in `LOG.md` (2026-11-23).

## 1. Universal shell and navigation

- Header: Academy name, current page, language switch, current user menu.
- One Academy-owned sidebar, **not** the Hub navigation.
- Learner destinations: **لوحتي / Dashboard**, **دوراتي / My Courses**,
  **إنجازاتي / Achievements**.
- Training Management destinations, shown individually by effective capability:
  **الدورات والمحتوى** (`academy.manage_content`),
  **التكليفات** (`academy.assign`),
  **التقارير** (`academy.view_reports`).
- System Management destinations: **الصلاحيات** and **سجل التدقيق**
  (`academy.admin` with appropriate scope).
- Integrated mode: optional **العودة إلى Hub** link; never an extra login.
- Standalone mode: simple local login and logout; no Hub link.
- Hide unauthorized links **and** deny unauthorized routes, actions, queries,
  and objects on the server. The sidebar must not assume Hub role-based admin rights.

## 2. Screen inventory and acceptance contract

| ID | Screen | Main content | Primary action | Access | Visual reference |
|---|---|---|---|---|---|
| L1 | My Dashboard / لوحتي | Due assignments, active courses, progress, last activity | Continue learning | Active `academy.learn` | New; reuse PDF card language |
| L2 | My Courses / دوراتي | Own enrollments, status, due date, progress | Open course | `academy.learn`, own data | New; reuse PDF cards |
| L3 | Course Details / تفاصيل الدورة | Description, ordered outline, locks, progress | Start/resume | `academy.learn`, enrolled user | New; derive from E |
| E | Lesson Player / مشغل الدرس | Video, lesson outline, progress, acknowledgment where configured | Complete/next | `academy.learn`, unlocked lesson | PDF p.21 |
| L4 | Achievements / إنجازاتي | Completed courses, completion dates | View completion | `academy.learn`, own data | New; reuse cards |
| A | Course Management / إدارة الدورات | Courses, status, filters, new-course action | Create course | `academy.manage_content` | PDF p.5 |
| B | Course Editor / إنشاء وتحرير دورة | Title, description, owner department, cover, acknowledgment | Save/next | `academy.manage_content` | PDF p.11 |
| C | Lessons & Media / الدروس والوسائط | Ordered lessons, upload status, add/edit lesson | Add lesson | `academy.manage_content` | PDF p.16 |
| D | Assignments / التكليفات | Course, target, due date, requirement, recipient count preview | Create assignment | `academy.assign` | PDF p.17 |
| F | Reports / التقارير | Course/department metrics, overdue list, filters, CSV | View/export | `academy.view_reports` | PDF p.22 |
| G | Permissions / الصلاحيات | User, individual grant, capability, scope, expiry, status | Grant/revoke | `academy.admin` | Existing G + p.17 dialog |
| S1 | Audit / سجل التدقيق | Actor, action, object, date, filters | Filter/export | `academy.admin` | Reuse table from p.22 |
| X1 | Local Login / الدخول المحلي | Username, password, validation | Sign in | Standalone only | Existing account-screen pattern |
| X2 | Access Denied / الوصول موقوف | Clear denial and safe return/logout | Return/logout | Blocked/inactive | Existing account-screen pattern |

**Scope guard:** These are **screen requirements**, not claims that the named
routes already exist. Do not add quiz-taking or certificate-issuing screens to H1.

## 3. Detailed learner contracts

### L1 — My Dashboard
- Purpose: immediate personal starting point after authenticated entry.
- Blocks: brief welcome, active/overdue assignments, in-progress courses,
  completion summary, most relevant Continue button.
- Empty: explain that no training is assigned; provide a safe My Courses link.
- Privacy: show only the current user's enrollments and progress.
- Integrated: open directly from Hub with no intermediate welcome/login screen.
- Standalone: open after successful local login.

### L2 — My Courses
- Course cards: title, state (`not_started`, `in_progress`, `completed`,
  `cancelled` where relevant), progress, due date if assigned.
- Filters: All, In Progress, Completed; overdue identified by text and icon.
- Click: opens L3. Never display another employee's enrollment.
- Empty: localized message, no fabricated training catalog requirement.

### L3 — Course Details
- Summary: title, description, progress, ordered sections/lessons.
- Lesson rows distinguish unlocked, locked and completed using text + icon.
- Start/Resume opens E at the next permitted position.
- Server controls lesson access; a disabled UI button is not authorization.

### E — Lesson Player
- Keep the existing approved p.21 layout and the player controls described in
  `docs/ui/wireframes.md` and `ARCHITECTURE.md` §7.
- Video first on mobile; outline and acknowledgment follow.
- Resume position, progress, captions when supplied, explicit completion state.
- Forward seeking/lesson unlocking is server-authoritative.
- On network trouble show retry/connection guidance without false completion.

### L4 — Achievements
- Completed course title, completion date, view-details action.
- Preserve completed records after Hub deactivation/reactivation.
- No certificate issuance control in H1 (CHARTER Phase 2).

## 4. Detailed management contracts

### A–C — Content management
- A lists courses with status and filters; action Create Course.
- B edits title, description, department ownership, cover, acknowledgment.
- C manages sections/lessons, ordered media, upload progress, retry/error.
- Save, Publish, Archive require explicit states/confirmation where destructive.
- All mutations recheck `academy.manage_content` and resource scope.

### D — Assignments
- Choose course, individual/department/role target as allowed by current contract,
  due date, mandatory/optional; show recipient **count**, not an invented roster.
- Preview and submit; confirmation names course and target.
- Cancel action requires explicit confirmation; affected unfinished enrollments
  follow the existing domain contract.

### F — Reports
- Filter by course, department and status within authorized scope.
- Summary cards and table show completion/overdue with textual status.
- CSV export checks `academy.view_reports` and logs the audited export.

### G — Permissions
- In `grants_only`, management authority comes from active Academy grants,
  **not** Hub `platform_admin` or `department_manager` roles.
- Display user, capability, department scope, expiry, status, grant/revoke.
- Admin can delegate only within their own effective admin scope.
- Preserve revoked history and prevent loss of the last effective admin.
- Any Academy local suspension must be distinguishable from revoked grants;
  suspension is lifted manually by an authorized Academy admin.

### S1 — Audit
- Filters: actor, action, object, date; export when authorized.
- Read-only, chronological, no user-facing delete action.
- Show reason/context for local administrative suspension events when supported.

## 5. Responsive and interaction rules

| Context | Required behavior |
|---|---|
| 360–767 px | One column; accessible drawer; management rows become labeled cards |
| 768–1023 px | Flexible card grid; no clipped controls |
| 1024 px+ | Sidebar and wider management tables; player outline beside video |
| RTL Arabic | Right-to-left reading/navigation, mirrored directional icons, correct mixed text |
| LTR English | Same functions, translated labels, natural left-to-right layout |
| Keyboard | Visible focus, labeled fields, accessible dialogs, 44×44 px touch targets |
| Feedback | Loading, empty, retryable error, forbidden, not found, slow/offline |
| Security | Permission checks at route, service and object/query scope |

Keep the PDF visual tokens: navy `#101820`, gold `#E8AA23`,
canvas `#F8FAFC`, white cards `#FFFFFF`, border `#E2E8F0`,
12 px rounded panels and a 4 px spacing scale. Accessible text colors
must meet contrast requirements; do not use brand gold as small text on white.

## 6. Three essential user journeys

1. **Employee:** Hub verified session **or** local login → L1 → L2/L3 →
   E → completion → L4.
2. **Training manager:** L1 → A → B → C → Publish → D → F,
   with each destination individually gated by its capability.
3. **Academy admin:** L1 → G → grant/revoke and scope review → S1 audit.
   No multi-organization onboarding or platform-admin screen.

## 7. Documentation and implementation boundaries

The documentation aligns `CHARTER.md`, `ARCHITECTURE.md`,
`docs/decisions.md`, `docs/hub-contract.md` and `docs/ui/wireframes.md`
with these screen requirements. This is a **documentation alignment**, not
proof that routes, screens, local account linking, suspension, or membership
reconciliation are implemented.

Before coding, check existing routes, migration constraints, and the current
Hub owner contract. The original PDF screens A–G remain the visual source;
L1–L4, S1, X1/X2 are **specified** but do not yet have owner-approved
pixel-perfect mockups.

### Implementation follow-up checklist (not a blocker to accepting documentation)

- [x] Documentation package: CHARTER §§2, 6, 6.1, 10 updated for the H1 target;
      adopted as charter 2.3 and recorded in `LOG.md`.
- [x] Documentation package: ARCHITECTURE §§13, 22 and 24 aligned with H1 target.
- [x] Documentation package: `docs/decisions.md` D-011 confirmed for Academy navigation.
- [x] `docs/domain-model.md`: re-enrollment uses a new row behind the partial unique index;
      local suspension state is `AccessSuspension` (§2.15).
- [x] Documentation package: `docs/hub-contract.md` clarified without inventing endpoints.
- [x] Documentation package: `docs/ui/wireframes.md` links this specification and preserves A–G.
- [x] On repository adoption: the `[CHARTER CHANGE]` entry is in `LOG.md` and the adoption is
      recorded; no implementation task status was changed by this documentation work.
- [ ] Verify visual references and UI text against the approved PDF before coding (T-013,
      T-023).

## 8. Deferred after H1

Quiz UI, certificates, advanced analytics, multi-organization management,
subscriptions, white-label, mobile apps, AI, marketplace, and speculative
administrative workflows.
