# Screen map and visual gate record

**Status:** Official UI/UX package v1.0 adopted 2026-11-25 (D-045); `R05-master` is the
controlling internal reference. No screen group gate is closed merely because the package arrived:
each group needs the owner's implementation-ready approval (or a written waiver) recorded here.
**Scope:** reference mapping, layout reading order and gate status. Identity, shell and components
are owned by `design-system.md`; screen behaviour and states by `screen-specification.md`;
fingerprints and archive by `design-reference.md`.

## 1. Reference boards

| Board | Covers |
|---|---|
| R01-public | Public landing hero; ignore internal panels |
| R02-login | Login and invitation acceptance |
| R03-recovery | Password reset request/sent/confirm/result |
| R04-verification-mfa | Email verification, TOTP setup/challenge and recovery |
| **R05-master** | **Controlling internal shell**: charcoal sidebar, white header, light canvas, white cards, gold accents, no banner |
| R06-platform | Platform overview and companies |
| R07-people-rbac | Employees, departments, roles and permission forms |
| R08-company | Company dashboard and training overview |
| R09-company-detail | Company detail and managers |
| R10-department | Department dashboard and assignment list |
| R11-builder-player | Course builder, assignment form and lesson player |
| R12-reports | Reports, notifications and settings |
| R13-catalog | Course/programme list and assignments |
| R14-learner | Learner dashboard and shared screens |

All screens use the single master shell; boards other than R05 illustrate content, not alternative
shells.

## 2. Screen → reference → task

The package's `SCREEN_INDEX.csv` was written against charter 2.3 and its task column is
provisional. The mapping below is reconciled with `docs/plan.md`; plan dependencies win.

| Package IDs | Screens (repository IDs) | Reference | Task | Gate status |
|---|---|---|---|---|
| PUB-01 | P1 Home, P3 Programmes | R01 | T-029 | pending group approval |
| AUTH-01/02 | X1 Login, X5 Accept invitation | R02 | T-029 | pending group approval |
| AUTH-03 | X2/X3 Reset request and confirm | R03 | T-029 | pending group approval |
| AUTH-04 | X4 Verify email | R04 | T-029 | pending group approval |
| AUTH-05 | TOTP setup/challenge/recovery (UI for T-027 contracts) | R04 | T-029 after T-027 | pending group approval |
| PL-01/02 | N5 Platform overview, N6 Companies | R06 | T-030 | pending group approval |
| PL-03 | N6 Company detail and managers | R09 | T-030 | pending group approval |
| CO-01 | Company dashboard (T-030 entry) | R08 | T-030 | pending group approval |
| CO-02 | N1 Members, invitations, member detail | R07 | T-030 | pending group approval |
| CO-03 | N3 Departments | R07 | T-030 | pending group approval |
| RB-01 | N2 Roles, permission matrix, assignments, grants | R07 | T-030 (API by T-028) | pending group approval |
| TR-01 | A Courses and programmes | R13 | T-031 | pending group approval |
| TR-02/03 | B Course builder, C Lessons and media | R11 | T-031 | pending group approval |
| AS-01/02 | D Assignments list/create/preview/cancel | R11 | T-031 | pending group approval |
| DP-01 | Department-head and training-manager dashboard | R10 | T-031 | pending group approval |
| LE-01/03 | L1 Dashboard, L2 My Courses, L4 Achievements/history | R14 | T-031 | pending group approval |
| LE-02 | L3 Course detail, E Player, completion | R11 | T-031 | pending group approval |
| RP-01 | F Reports, filters, CSV | R12 | T-032 | pending group approval |
| NT-01 | Notifications | R12 | T-032 | pending group approval |
| SH-01 | Profile, account, security, language | R12 | T-029 | pending group approval |
| SH-02 | N4 Company settings, N8 Platform settings | R12 | T-030 | pending group approval |
| SH-03 | S1/S2 Audit and retention | text only | T-030 | pending text approval |
| SH-04 | X6 403, 404, 500, loading, empty, dialogs | text only | T-029 | pending text approval |

`SH-03`/`SH-04` have no board; their content contract is `screen-specification.md` §4–§5. A group
may be implemented only after its row records an owner approval date plus package version, or an
explicit waiver. A waiver is never a claim of pixel compliance.

Acceptance for every group is its task card in `docs/plan.md` plus visual acceptance V01–V11 in
`docs/ui/design-system.md`, with the screen-specific states and responsive behaviour from
`screen-specification.md` §3–§6.

## 3. Layout reading order

| Group | Mobile 390 (base) | Tablet 768 | Desktop 1440 |
|---|---|---|---|
| Public / auth | Single column; form or hero first; architecture panel below or omitted | Wider form, split hero | Split composition; form card centred |
| Application shell | 56 px header, drawer, bottom navigation (max four + More) | 64 px header, drawer or 72 px rail | 64 px header, persistent 240 px sidebar |
| Dashboards | KPI cards stacked (two columns only if labels fit), then lists | Two-column cards | 12-column grid, four KPI cards where space permits |
| Administration | Filters in a sheet, rows as labelled cards, actions in the card menu | Wider cards, table where readable | Data table with actions menu; details in a drawer/dialog |
| Course builder / player | Stepper/accordion; player first, outline below | Split sections | Outline beside editor; player beside outline |
| Reports / notifications | Filters sheet, cards, accessible chart summary | Two-column summary | Table plus filters; chart with table alternative |
| Dialogs | Full-screen or sheet, actions reachable, focus trapped | Centred dialog | Centred dialog with explicit cancel |

## 4. Preview routes

In development, `/academy/preview/` hosts the T-013 shell and sample states at
`/academy/preview/ar/` and `/academy/preview/en/`. Append `?state=loading`, `?state=empty`,
`?state=error`, `?state=forbidden`, or `?state=slow` for the corresponding sample; use
`?dialog=grant&state=validation` for a field error. The A–G, L1–L4 and S1 screens arrive with the
tasks that implement them. Preview data is sample data and writes nothing.

The preview still carries the interim T-013 palette and font; T-029 migrates it to
`design-tokens.json` and the Rubik asset when the owner supplies the font. Until then the preview is
a behaviour fixture, not a visual reference.

## 5. Superseded visual language

The earlier interim PDF (`masheed-academy-screens.pdf`, pages 1–22), its sampled palette and its
A–G wireframes are **superseded** and archived outside the repository (`design-reference.md` §4).
They are not a source for colours, layout or components. The T-013 stylesheet still contains the old
values; that is a known implementation gap that T-029 closes, not an approved reference.

## 6. Out of scope in references

Board content does not add scope. Not approved by appearing in an image: self-registration, SSO,
company switching or a company chooser, plans/pricing/billing, impersonation, certificates, quizzes,
personal notes, a custom report builder, PDF/Excel export, new approval workflows, analytics or
sample identities, avatars and metrics. Current scope and permissions remain
`CHARTER.md`, `docs/access-control.md` and `screen-specification.md`.
