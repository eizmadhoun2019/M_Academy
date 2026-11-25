# Masheed Academy — H1.5 Screen Specification

> **Status:** Adopted 2026-11-25 (charter 2.5). Specifies the **target**, not verified
> implementation. Mobile first and the official visual reference are binding (D-044).
> **Scope:** standalone-first multi-company platform: public site on `/`, protected application
> under `/academy/`. Masheed is the first company, not the only one.
> **Visual source:** approved identity set: Primary `#101820`, Brand Gold `#E8AA23`, Rubik, the
> official Masheed logo and gold geometric element, dark geometric backgrounds and light internal
> surfaces with dark navigation and gold accents. The final screen/token package is **not yet
> delivered**; the interim `docs/ui/reference/masheed-academy-screens.pdf` covers A–G only.
> `docs/ui/wireframes.md` holds the layout map and design-gate record. No document claims the
> final package is approved.
> **Authority:** CHARTER > RULES > ARCHITECTURE > this file. Routes and API are in
> `docs/api.md`; permissions in `docs/access-control.md`.

## 1. Universal shell
- **Public shell** (`/`): academy name, programme links, contact, language switch, **Sign in**
  (`/academy/login/`). No session, no application data, no UUID.
- **Application shell** (`/academy/`): academy/company name (read-only, from the single
  membership), page title, language switch, notifications, user menu (profile, security, sign
  out). There is no company switcher or company chooser. A platform-only account sees platform
  navigation and an explicit company selector only inside company-scoped platform screens.
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
| X6 | Access denied `/academy/denied/` | Reason code, safe return, sign out | authenticated or blocked |

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
- Shows only the caller's enrollments in the company derived from their single membership; no
  cross-company counts and no company switch.
- A learner with no active membership lands on X6 with `membership_inactive`; a platform-only
  user is routed to the platform area instead.

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
`forbidden` (X6 with reason), `not_found`, `rate_limited` (retry-after), `server_error`
(correlation id), `timeout`, `offline` (retry), `disabled` (reason visible), `confirmation`
(names the object and effect), `unknown_outcome` (verify before retry; never claim success).
- Never show success before the response; disable submit while in flight; a repeated submit is
  idempotent server-side.
- Errors never include stack traces, SQL, tokens, emails or another company's data.
- Destructive actions require confirmation and, for admin actions, a reason.

## 6. Mobile-first responsive, language and accessibility
Design and implementation order is **Mobile → Tablet → Desktop → Large Desktop**. Every screen,
including public, auth, dashboards, platform/company administration, learning, reports and
settings, is first designed and built at Mobile. Desktop is never the base design shrunk down.

| Reference width | Required behavior |
|---|---|
| **320 px minimum** | Supported intermediate width; no clipped content, controls or unusable tables |
| **Mobile 390 px** | One column; drawer/bottom navigation; management rows become labelled cards; actions stay reachable; no unjustified page-level horizontal scroll |
| **Tablet 768 px** | Flexible grid; wider forms and tables; no clipped controls; a table may scroll inside its own labelled container |
| **Desktop 1440 px** | Persistent sidebar; wide tables; player outline beside video; same functions as Mobile |
| **Large Desktop >1440 px** | Content max-width and spacing scale; no stretched line lengths or empty over-wide panels |

| Requirement | Acceptance |
|---|---|
| Reflow | Content is reorganized per width, not merely scaled; no lost core function on Mobile |
| Overflow | No unjustified page-level horizontal scrolling at 320/390/768/1440 px in ar/en |
| Touch | Minimum 44×44 px targets with adequate spacing; no hover-only action |
| RTL / LTR | Arabic RTL and English LTR mirror direction, icons, mixed text and numbers correctly |
| Keyboard | Visible focus, logical order, labelled fields, accessible dialogs, Escape closes |
| Screen reader | Landmarks, headings, table captions, status announcements, meaningful alt text |
| Contrast | WCAG AA (4.5:1 text, 3:1 large text/UI); never colour alone; gold is not small text on white |
| Content | Clear labels and one primary action per task; tables/forms/reports remain comprehensible on Mobile |

Approved identity constants are Primary `#101820`, Brand Gold `#E8AA23` and **Rubik** (Arabic +
Latin, locally hosted). The final package supplies the complete tokens (spacing, type scale,
radii, elevation, component states); until then the interim values in `docs/ui/wireframes.md`
apply and are not a final-brand claim.

## 7. Visual-reference gate (per screen group)
1. **Grouping:** P1–P5; X1–X6; application shell + L1–L4/E; A–D/F; N1–N4/S1; N5–N8/S2. A group is
   implemented only after its approved screen references are recorded in `docs/ui/wireframes.md`.
2. **Required package:** Screen Designs, Design Tokens, Typography, Colors, Spacing, Components,
   Responsive Layouts (320/390/768/1440), Interaction States, Accessibility Requirements and
   Visual Acceptance Criteria. Images alone are not an engineering specification.
3. **Approval:** the owner approves the group in writing (date + package version) or records an
   explicit waiver. The waiver is not a claim of pixel compliance.
4. **Binding:** approved designs are implementation specifications. No redesign, identity change or
   element rearrangement without owner approval.
5. **Verification:** visual regression compares rendered screens with the approved references at
   the supported widths; T-034 requires the comparison evidence. Backend tasks proceed without
   waiting for a design group.
6. **Status:** the final package has **not** been delivered. A–G use the interim PDF; all other
   groups use the token system and documented patterns and must pass the gate before UI work.

## 8. Essential journeys

1. **Learner:** `/academy/login/` → L1 → L2/L3 → E → completion → L4.
2. **Training manager:** L1 → A → B → C → publish → D → F, each step gated by its permission.
3. **Company Admin:** N1 invite → N2 role → N3 department → N4 settings → S1 audit.
4. **Super Admin:** N5 → N6 create company + first admin → audited read-only access → S2.
5. **Public visitor:** P1 → P3 → Sign in; no session and no application data.

## 9. Boundaries
This document aligns CHARTER, ARCHITECTURE, decisions, API and wireframes; it is **not** proof
that routes or screens exist. Before coding, check current routes, migrations and permissions.
L1–L4, N1–N8, S1–S2, P1–P5 and X1–X6 do not all have final owner-approved references; A–G use
the interim PDF, the rest use the token system and documented patterns, and every group must pass
the §7 gate before implementation. No design package is claimed as delivered or approved. Quiz, certificates, billing,
self-registration, advanced analytics, mobile apps and AI are deferred.
