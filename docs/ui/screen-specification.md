# Masheed Academy — H1.5 Screen Specification

> **Status:** Adopted 2026-11-25 (charter 2.4). Specifies the **target**, not verified
> implementation.
> **Scope:** standalone-first multi-company platform: public site on `/`, protected application
> under `/academy/`. Masheed is the first company, not the only one.
> **Visual source:** `docs/ui/reference/masheed-academy-screens.pdf` (23 pages) for A–G;
> `docs/ui/wireframes.md` for the wireframe map and layout rules.
> **Authority:** CHARTER > RULES > ARCHITECTURE > this file. Routes and API are in
> `docs/api.md`; permissions in `docs/access-control.md`.

## 1. Universal shell
- **Public shell** (`/`): academy name, programme links, contact, language switch, **Sign in**
  (`/academy/login/`). No session, no application data, no UUID.
- **Application shell** (`/academy/`): academy/company name, page title, company switcher (only
  when the user has more than one active membership), language switch, notifications, user menu
  (profile, security, sign out).
- **One Academy-owned sidebar**, never a Hub navigation mirror. Groups and items are rendered
  from effective permissions; hiding is not authorization.
- Learner: **لوحتي / Dashboard**, **دوراتي / My Courses**, **إنجازاتي / Achievements**.
- Training management (each item by permission): **الدورات والمحتوى** (`academy.content.view`),
  **التكليفات** (`academy.assignment.view`), **التقارير** (`academy.report.view`).
- Company administration: **الأعضاء** (`academy.member.view`), **الأقسام**
  (`academy.department.manage`), **الأدوار والصلاحيات** (`academy.role.manage` or
  `academy.grant.manage`), **الإعدادات** (`academy.settings.manage`), **سجل التدقيق**
  (`academy.audit.view`).
- Platform administration (Super Admin): **نظرة عامة**, **الشركات**
  (`platform.organization.view`), **مستخدمو المنصة** (`platform.user.manage`), **تدقيق المنصة**
  (`platform.audit.view`), **إعدادات المنصة** (`platform.settings.manage`).
- No link appears without its permission, and every route rechecks it server-side.

## 2. Screen inventory

### Public (no session)
| ID | Screen | Content | Primary action |
|---|---|---|---|
| P1 | Home `/` | Academy intro, mission/vision, features, programme areas, how to benefit, contact, sign-in | Sign in / explore programmes |
| P2 | About `/about/` | Story, mission, approach, partners (approved copy only) | Contact |
| P3 | Programmes `/programmes/` | Public programme/category list (no learner data) | Sign in to view training |
| P4 | Contact `/contact/` | Platform support contact and working hours (`docs/configuration.md`) | Open mail client |
| P5 | Privacy & Terms `/privacy/`, `/terms/` | Current policy text, last-updated date | Back |

### Authentication
| ID | Screen | Main content | Access |
|---|---|---|---|
| X1 | Login `/academy/login/` | Email, password, “forgot password”, language | anonymous |
| X2 | Forgot password `/academy/password/reset/` | Email field, neutral confirmation | anonymous |
| X3 | Reset confirm `/academy/password/reset/<token>/` | New password + confirmation | token |
| X4 | Verify email `/academy/verify/<token>/` | Result and continue | token |
| X5 | Accept invitation `/academy/invite/<token>/` | Name, password, company name (read-only) | token |
| X6 | Choose company `/academy/select-company/` | Active memberships only; disabled/suspended companies are not selectable | authenticated, >1 membership |
| X7 | Access denied `/academy/denied/` | Reason code, safe return, sign out | authenticated or blocked |

### Learner
| ID | Screen | Main content | Primary action | Permission |
|---|---|---|---|---|
| L1 | Dashboard | Due/overdue assignments, in-progress courses, completion summary, next action | Continue learning | `academy.learn` (SELF) |
| L2 | My Courses | Own enrollments, status, due date, progress, filters | Open course | `academy.learn` |
| L3 | Course details | Description, ordered outline, locks, progress | Start/resume | `academy.learn`, enrolled |
| E | Lesson player | Video, outline, progress, acknowledgment, completion | Complete / next | `academy.learn`, unlocked lesson |
| L4 | Achievements | Completed courses and dates | View details | `academy.learn`, own data |

### Training management
| ID | Screen | Main content | Primary action | Permission |
|---|---|---|---|---|
| A | Courses | Company courses, status, filters, owner department | Create course | `academy.content.view` (+ manage for write) |
| B | Course editor | Title, description, department, cover, acknowledgment | Save | `academy.content.manage` |
| C | Lessons & media | Ordered sections/lessons, upload/transcode state, retry | Add lesson | `academy.content.manage` / `academy.media.manage` |
| D | Assignments | Course, target, due date, mandatory, recipient count | Create assignment | `academy.assignment.manage` |
| F | Reports | Summary, overdue, completion, filters, CSV | Export | `academy.report.view` / `.export` |

### Company administration
| ID | Screen | Main content | Primary action | Permission |
|---|---|---|---|---|
| N1 | Members | Search, membership state, departments, roles, invitations | Invite / suspend / remove | `academy.member.view` / `.manage` |
| N2 | Roles & grants | Roles, members, effective access, exceptional grants, expiry | Assign / grant / revoke | `academy.role.manage` / `academy.grant.manage` |
| N3 | Departments | Tree, member counts, archive state | Create / rename / re-parent / archive | `academy.department.manage` |
| N4 | Company settings | Name, language, time zone, reminder hour, sender name, general-course label | Save | `academy.settings.manage` |
| S1 | Company audit | Actor, action, target, date, company; filters | Filter (export if allowed) | `academy.audit.view` |

### Platform administration
| ID | Screen | Main content | Primary action | Permission |
|---|---|---|---|---|
| N5 | Platform overview | Company count/state, active members, platform health summary | Open company | `platform.organization.view` |
| N6 | Companies | Create company, first Company Admin, suspend/reactivate/archive, read-only access | Manage company | `platform.organization.manage` / `.access` |
| N7 | Platform users | Platform role assignments, last-admin guard | Assign / revoke | `platform.user.manage` |
| S2 | Platform audit | Platform-scoped events, filters | Filter | `platform.audit.view` |
| N8 | Platform settings | Site name/support contact, integration enablement (Hub flag), read-only state | Save (audited) | `platform.settings.manage` |

**Scope guard:** these are requirements, not claims that routes exist. Quiz-taking, certificates,
billing, self-registration and white-label screens are out of H1.5.

## 3. Detailed learner contracts
### L1 — Dashboard
- Blocks: welcome with display name, overdue/next-due assignments, in-progress courses, completion
  summary, one primary **Continue** action.
- Empty: explains that no training is assigned and links to My Courses; never fabricates content.
- Shows only the caller's enrollments in the active company. Switching company reloads with that
  company's data; no cross-company counts.
- A learner with no active membership lands on X7 with `membership_inactive`.

### L2 — My Courses
- Cards: title, state (`not_started`, `in_progress`, `completed`, `cancelled` where relevant),
  progress, due date; overdue marked by text + icon, not colour alone.
- Filters: All, In Progress, Completed, Overdue.
- No other learner's enrollment is reachable by id (server 404).

### L3 — Course details
- Title, description, progress, ordered sections/lessons.
- Each lesson row shows unlocked/locked/completed with text + icon.
- Start/Resume opens E at the next permitted position; direct URL to a locked lesson shows the
  lock reason, never the content.
- Completion requires the server's threshold/lesson sequence; UI never unlocks optimistically.

### E — Lesson player
- Video first on mobile; outline and acknowledgment below.
- Resume position, progress, captions when supplied, explicit completed state.
- Forward seeking and unlock are server-authoritative (heartbeat/frontier).
- Network trouble: retry guidance, no false completion, no lost progress beyond the confirmed
  frontier.
- Playback URL expiry shows a recoverable “reload” action, not a broken player.

### L4 — Achievements
- Completed course, completion date, method (lessons/override) and view action.
- Completion history survives membership removal or company archive; access follows the
  membership lifecycle.
- No certificate control in H1.5.

## 4. Detailed management contracts
### A–C — Content
- A: company-scoped list, status filter, owner department; Create only with
  `academy.content.manage`.
- B: title, description, owner department (within scope), cover, acknowledgment; validation
  inline; save never publishes.
- C: sections/lessons reorder, media upload with progress/retry, transcode states; publishing
  requires `academy.content.publish` and shows validation errors by lesson.
- Archive requires confirmation and explains the effect on assignments.

### D — Assignments
- Course (within scope), target department(s)/members, due date (company time zone), mandatory.
- Recipient **count** preview from the server; no invented roster. Confirmation names course,
  target and due date.
- Cancel requires confirmation; the effect on unfinished enrollments follows the domain contract.

### F — Reports
- Summary/overdue/completion tabs, filters by course, department and status within scope.
- Textual status and accessible tables; CSV export checks `academy.report.export`, is audited and
  is disabled while an export is in flight.
- Platform users see the platform summary only through N5/N6, with an explicit company filter.

### N1 — Members
- List: name, email, state (`invited`, `active`, `suspended`, `removed`), departments, roles,
  last activity.
- Invite: email + role + departments; resend; revoke invitation.
- Suspend/remove requires a reason, is confirmed, cancels access immediately and preserves history.
- Last Company Admin cannot be suspended, removed or demoted: action disabled with the reason and
  a server 409 if forced.

### N2 — Roles & grants
- Tabs: members' roles, role catalogue, exceptional grants.
- Shows effective permissions at their scope; assignment cannot exceed the actor's own access.
- Platform permissions never appear in a company role editor.
- Grant: permission, scope (department/self where allowed), expiry, reason; revoke keeps history.
- Every change requires confirmation and writes audit.

### N3 — Departments
- Tree with member counts; create, rename, re-parent (cycle and cross-company rejected), archive.
- Archive is blocked while active assignments/members depend on it; the reason is shown.
- A department manager sees only their subtree.

### N4 — Company settings
- Name, default language, time zone, reminder hour, sender name, general-course label, support
  email/phone for P4.
- Changes are audited and affect new messages immediately; existing local dates re-render in the
  new zone without changing stored UTC values.

### S1/S2 — Audit
- Filters: actor, action, target type, date range. Read-only, chronological, no delete.
- Company view never shows another company's events; platform view is platform-scoped and shows
  audited company access.

### N5–N8 — Platform
- N5: company list with state, active members, courses, last activity; no learner-level data.
- N6: create company + first admin invitation; suspend/reactivate/archive with reason and
  confirmation; **read-only company access** is visibly marked (banner) and every access is
  audited. Write actions are absent in that mode.
- N7: platform role assignments; last platform admin protected (server 409).
- N8: site identity and integration flags; enabling Hub requires confirmation and a reason,
  and is disabled unless the full integration configuration is present.

## 5. UI state contract
Every screen implements these states explicitly; no blank page and no false success:
`loading` (skeleton/spinner), `empty` (explanation + next action), `success` (confirmed by the
server), `validation_error` (field-level, preserves non-sensitive input), `unauthorized` (X1),
`forbidden` (X7 with reason), `not_found`, `rate_limited` (retry-after), `server_error`
(correlation id), `timeout`, `offline` (retry), `disabled` (reason visible), `confirmation`
(names the object and effect), `unknown_outcome` (verify before retry; never claim success).
- Never show success before the response; disable submit while in flight; a repeated submit is
  idempotent server-side.
- Errors never include stack traces, SQL, tokens, emails or another company's data.
- Destructive actions require confirmation and, for admin actions, a reason.

## 6. Responsive, language and accessibility
| Context | Required behavior |
|---|---|
| 360–767 px | One column; drawer navigation; management rows become labelled cards; no horizontal page scroll |
| 768–1023 px | Flexible grid; no clipped controls or tables without a scroll container |
| 1024 px+ | Persistent sidebar; wide tables; player outline beside video |
| Arabic (RTL) | Right-to-left navigation, mirrored directional icons, correct mixed-direction text and numbers |
| English (LTR) | Same functions and translated labels, natural left-to-right layout |
| Keyboard | Visible focus, logical order, labelled fields, accessible dialogs, Escape closes, 44×44 px targets |
| Screen reader | Landmarks, headings, table captions, status announcements, alt text for meaningful images |
| Contrast | WCAG AA (4.5:1 text, 3:1 large text/UI); never colour alone; brand gold is not small text on white |

Visual tokens: navy `#101820`, gold `#E8AA23`, canvas `#F8FAFC`, white `#FFFFFF`, border
`#E2E8F0`, 12 px rounded panels, 4 px spacing scale, Tahoma/Arial for Arabic.

## 7. Essential journeys
1. **Learner:** `/academy/login/` → L1 → L2/L3 → E → completion → L4.
2. **Training manager:** L1 → A → B → C → publish → D → F, each step gated by its permission.
3. **Company Admin:** N1 invite → N2 role → N3 department → N4 settings → S1 audit.
4. **Super Admin:** N5 → N6 create company + first admin → audited read-only access → S2.
5. **Public visitor:** P1 → P3 → Sign in; no session and no application data.

## 8. Boundaries
This document aligns CHARTER, ARCHITECTURE, decisions, API and wireframes; it is **not** proof
that routes or screens exist. Before coding, check current routes, migrations and permissions.
L1–L4, N1–N8, S1–S2, P1–P5 and X1–X7 do not all have owner-approved pixel-perfect mockups; A–G
use the PDF, the rest use the token system and existing patterns. Quiz, certificates, billing,
self-registration, advanced analytics, mobile apps and AI are deferred.
