# CHARTER — Project Purpose, Scope and Success

**Charter version:** 2.5 (multi-company standalone target; one company membership per account;
H1.5 inside GATE-1; Hub optional and dormant; mobile-first and the official visual reference are
binding)
**Approved by:** Project owner
**Last reviewed:** 2026-11-25

## 1. Identity and purpose
- **Project name:** Masheed Academy (Python package: `academy`).
- **Purpose:** One central, automated, trackable place to train employees across a company —
  every employee receives the same quality of onboarding and mandatory training, managers know
  exactly who completed what and when, and nobody chases people manually.
- **Problem:** Ad-hoc training wastes time and causes errors; managers cannot see completion;
  manual reminders consume management time; external LMS platforms mean per-seat recurring
  cost and training data leaving the organization's systems.
- **Product:** an independent, professional, secure, configurable, multi-company training
  platform with one public website, one authenticated application, local accounts and
  memberships, scoped permissions, auditable administration, bilingual Arabic/English UI and
  an API-first core. **Masheed is the first company on the platform, not the only company it
  supports.**
- **Horizons:** **H1.5** (this charter) standalone platform foundation: multi-company tenancy,
  local identity, dynamic RBAC, public site + application portal, training features, operations.
  **H2** commercialization: plans, subscriptions, billing, company self-registration,
  white-label. **H3** advanced: external SSO/SCIM, SCORM/xAPI, quizzes UI, certificates, AI.
  H1.5 must not block H2/H3, and must not build them early.
- **Governing principle:** *design for the future, implement for the present.* No
  microservices, extra abstraction layers, libraries or speculative features without a proven
  need and a recorded engineering rationale.

## 2. Goals
- G1 Deliver video-based courses through one local account that belongs to **at most one**
  company in H1.5; platform roles never create synthetic memberships.
- G2 Enforce sequential learning with server-verified progress (the browser is never trusted).
- G3 Isolate every company's data at every layer, with audited platform oversight.
- G4 Give managers scoped dashboards, reports and CSV export without manual chasing.
- G5 Let a company administer its own users, departments, roles and training.
- G6 Provide a professional public website and a separate, permission-aware application portal.
- G7 Build a modular, tested, documented foundation that can be operated, extended and
  commercialized without a rewrite.

## 3. Users and stakeholders
| Group | Role in the product |
|---|---|
| Learner | Consumes assigned training; owns only their enrollments and progress. |
| Training Manager | Authors and publishes content, assigns training and reads reports inside an authorized scope. |
| Company Admin | Administers one company: users, invitations, departments, roles, settings, audit. |
| Auditor | Read-only access to reports, content and audit within an authorized scope. |
| Super Admin (platform) | Manages companies, platform users and roles, platform audit; authorized, audited read access to company data. |
| Company IT / operations | Operates the deployment, storage, mail, backups and monitoring. |
| Project owner / management | Sponsor; approves scope, decisions, gates and UAT. |

The permission catalogue, default roles, scopes and enforcement rules live **only** in
`docs/access-control.md`. This charter states which roles exist, not what each may do.

## 4. Scope
### In scope (H1.5)
- Organizations as first-class entities; company departments; **one organization membership per
  account** (unique `user_id`), so a normal user has exactly one company context derived
  server-side. Platform administrators hold `PlatformRoleAssignment` and need no company row.
- Local identity: email + password, verification, password reset/change, invitations, session
  management, TOTP MFA for sensitive administrative accounts, recovery codes, login abuse
  protection, security audit. Custom User with Django Auth; no hand-written auth engine.
- Dynamic scoped RBAC: functional permissions, system and custom roles, multiple roles,
  exceptional grants, `PLATFORM`/`COMPANY`/`DEPARTMENT`/`SELF` scopes, deny by default,
  least privilege, last-admin protection.
- Public website on `/` (Arabic and English): introduction, vision, features, programmes,
  how to use, contact, privacy and terms, login entry point.
- Application under `/academy/`: independent sign-in and account screens, direct entry to the
  dashboard permitted by the user's roles, dynamic dashboard and sidebar, platform and company
  administration, training management, learning screens, reports, notifications, settings. No
  company-selection or company-switching screen or control exists.
- Course authoring with immutable versions, sections, lessons (video Phase 1; pdf/text Phase 2).
- Media upload + HLS processing (360p/720p, 6 s segments), optional captions, controlled playback.
- Assignment to membership/department/role/whole company, due dates, mandatory flag, auto-enroll
  when a membership becomes active.
- Server-authoritative progress, sequential locking, completion records.
- Notifications and reminders through a local, swappable mail transport (SMTP default).
- Reports and CSV export, scoped by company and department; audited platform aggregation.
- Append-only audit trail; privacy export/anonymization/retention for stored account data.
- Arabic (default, RTL) and English (LTR), WCAG 2.2 AA, responsive UI.
- Operational baseline: environments, CI/CD, health checks, structured logs, metrics, error
  monitoring, backups and a proven restore, runbooks.
### Out of scope (H1.5)
Billing, subscriptions, plans, company self-registration, white-label branding, custom domains,
SSO/SAML/OIDC providers, SCIM, live streaming, forums, gamification, quizzes UI, certificates,
mobile apps, AI, marketplace, advanced analytics warehouse, multi-region data residency.
Hub integration is built and tested but **dormant**; it is not a launch dependency.

## 5. Requirements
Requirement IDs are stable. Acceptance criteria are proven by automated tests or recorded
manual checks before a gate closes. Detailed task mapping: `docs/plan.md`; coverage:
`docs/traceability.md`.

| ID | Requirement | Priority | Acceptance criteria | Owner |
|---|---|---|---|---|
| REQ-01 | Foundation scaffold and CI quality gates | Must | Clean checkout runs via compose; G1–G12 green in CI | Tech authority |
| REQ-02 | Adapter layer + host stub with contract suites | Must | Identity/organization/notify/storage contracts pass for stub and HTTP fakes | Tech authority |
| REQ-03 | Full schema with migrations, tenant and identity integrity | Must | Every tenant table scoped; composite FKs prevent cross-company relations; migrations apply/reverse; isolation suite passes | Tech authority |
| REQ-04 | Domain events on commit + append-only audit | Must | Events fire only after commit; audit rows immutable at DB level; platform actions audited | Tech authority |
| REQ-05 | Bilingual mobile-first design system for public site and application | Must | One master shell and tokens committed; 320/390/768/1024/1440/1920 px in ar+en; no unjustified horizontal overflow; Mobile → Tablet → Desktop → Large Desktop order | Tech authority |
| REQ-06 | Course authoring, versions, publish | Must | ≥2 sections/lessons, publish validation, immutability, prior version archived | Tech authority |
| REQ-07 | Media upload → HLS processing → secure playback | Must | Presigned PUT; ffmpeg→HLS `ready`; failures retryable; playback authorized per learner and company | Tech authority |
| REQ-08 | Assignment + auto-enroll on membership change | Must | Target matrix, due date, mandatory flag; join/leave enrols and cancels | Tech authority |
| REQ-09 | Sequential locking + server-verified progress | Must | Lesson N+1 locked until N complete; forward skip rejected; ≥90% watched completes | Tech authority |
| REQ-10 | Completion + notifications exactly once | Must | Learner and manager messages, idempotent per dedupe key | Tech authority |
| REQ-11 | Reminders + escalation | Must | due−3/due/due+1 reminders; manager digest at due+3; idempotent; per-company time zone | Tech authority |
| REQ-12 | Scoped reports + CSV | Must | Completion %, overdue, average time per course/department; formula-safe CSV; cross-scope refused | Tech authority |
| REQ-13 | Permission grants and scoped authorization | Must | Allow/deny/scope matrix tested in API and web; denial audited; no client-supplied authority | Project owner |
| REQ-14 | Learner + management web UI | Must | Screens L1–L4, E, A–C, D, F, S1 per `docs/ui/screen-specification.md`; manual checks recorded | Tech authority |
| REQ-15 | Journey/E2E, accessibility, responsiveness | Must | Full journey test; Playwright at 320/390/768/1024/1440/1920 px in ar+en; axe zero critical/serious; visual regression against approved implemented baselines | Tech authority |
| REQ-16 | Operations | Must | Staging deploy from CI; daily backup; recorded restore drill; monitored `/healthz` with alerts | Tech authority |
| REQ-17 | Performance at design capacity | Must | Targets in `docs/performance-profile.yaml` met, or an owner-accepted deviation recorded | Project owner |
| REQ-18 | Security review | Must | OWASP ASVS L1 checklist complete; dependency and image scans clean; CSP and session controls verified | Tech authority |
| REQ-19 | Privacy tooling | Must | Account/membership export, anonymization and retention tested; every PII column registered | Project owner |
| REQ-20 | Pilot + management demo | Must | Pilot company completes a real course; feedback recorded and triaged | Project owner |
| REQ-21 | Companies, memberships and departments | Must | Create/suspend/archive company; one account has at most one membership (DB unique + service + tests); membership states separate from account; company context derived from membership; cross-company read/write refused in every layer | Project owner |
| REQ-22 | Local identity and account lifecycle | Must | Email verification, reset, change, invitations, session listing/revocation, TOTP MFA for admin roles, enumeration-safe errors, Argon2, no secret in logs | Project owner |
| REQ-23 | Dynamic scoped RBAC | Must | Permission catalogue, system + custom roles, multiple roles, `PLATFORM`/`COMPANY`/`DEPARTMENT(S)`/`SELF`, deny by default, escalation blocked, last platform/company admin protected, changes audited | Project owner |
| REQ-24 | Public website + application portal separation | Must | `/` public ar/en without session; app under `/academy/`; independent login; direct post-login dashboard; no company chooser; no UUIDs shown; language switch persists | Project owner |
| REQ-25 | Platform and company administration | Must | Super Admin manages companies/users/roles and targets a company by explicit id without membership; Company Admin manages only their company; every screen and action permission-driven | Tech authority |
| REQ-26 | Mail and notifications without Hub | Must | SMTP transport; verification/reset/invitation/reminder mail delivered; no Hub dependency to run the platform | Tech authority |
| REQ-27 | Observability and operational readiness | Must | Metrics, tracing correlation, error reporting, slow-query visibility; alert thresholds implemented; runbooks exist | Tech authority |
| REQ-28 | Migration and backward compatibility | Must | Existing organization/training/progress/completion/audit records preserved; legacy user references mapped to accounts; API compatibility policy applied | Tech authority |

## 6. Non-functional requirements
Full targets are owned by `docs/performance-profile.yaml`; architecture and measurements are
summarized in `ARCHITECTURE.md`. Baseline: 10 companies / 5,000 registered users / 500
concurrent viewers / 50 concurrent administrators; API p95 < 300 ms (heartbeat p95 < 150 ms);
LCP ≤ 2.5 s, CLS ≤ 0.1, INP ≤ 200 ms on a mid-range phone over 4G; availability 99.5% monthly;
RPO ≤ 24 h, RTO ≤ 4 h; OWASP ASVS L1 + WCAG 2.2 AA; latest two versions of Chrome, Edge,
Firefox, Safari and Samsung Internet; ar (default, RTL) + en; coverage ≥ 85% on business-logic
packages. **Mobile first is mandatory for every screen:** design and implement Mobile (390 px),
then Tablet (768 px), Desktop (1440 px) and Large Desktop, and verify **320, 390, 768, 1024,
1440 and 1920 px** in both Arabic RTL and English LTR. Desktop is never the base design shrunk
down; core functions, forms, tables and reports must remain usable and accessible with no
unjustified page-level horizontal scrolling. Tokens and the single master shell are in
`docs/ui/design-system.md`.

## 7. Project profile
### Scale
**Medium.** Multi-company from day one, one deployment per environment. Indicators: 10
companies, 5,000 learners, 500 concurrent video viewers, ~33 heartbeat req/s, background
workers, object storage, bilingual UI, one public site plus an authenticated portal.

### Sensitivity
**Sensitive.** Employee accounts (email is now stored for authentication), training behaviour,
membership data and audit trails under employee-monitoring rules; company isolation is a
security boundary; append-only audit and platform oversight require strict authorization.

### Performance profile
Canonical location: `docs/performance-profile.yaml` (owned by this charter).

## 8. Constraints and dependencies
- Django 5.2 + PostgreSQL 16 + Redis + Celery, server-rendered templates and vanilla ES
  modules; no SPA build step. Technologies change only with an owner-approved decision.
- One image promoted across environments; 12-factor configuration; secrets from the
  environment or a secret manager.
- **Own repository** (`M_Academy`) with its own history and no legacy imports. The legacy
  `Masheed-Academy` repository and deployment are reference only and stay untouched.
- **Own runtime stack.** Compose project `m-academy` with its own containers, PostgreSQL,
  Redis, object storage, buckets, volumes, broker and secrets, on its own ports. It must run
  beside any existing stack without sharing or disturbing it
  (`docs/operations/environments.md`).
- Hub is an **optional integration** (signed identity, directory, mail/activity, membership
  webhooks). Disabled by default; no connection, synchronization or background job while
  disabled; its routes are unavailable; it is not required to run or release the platform.
  Reactivation needs a formal decision, security review and acceptance tests
  (`docs/hub-contract.md`).
- Open owner decisions are tracked only in `docs/decisions.md`.

## 9. Success measures
| Measure | Baseline | Target | Measurement method | Owner |
|---|---|---|---|---|
| Mandatory-course completion within 30 days of assignment | TBD (owner, before pilot) | ≥ 90% | Reports query per course | Project owner |
| Manager time on training follow-up | TBD | reduced by [X] hours/month | Manager survey (pilot, T-034) | Project owner |
| New hires with onboarding complete within 2 weeks | TBD | ≥ [X]% | Reports query | Project owner |
| External LMS subscription cost for covered use cases | current spend | eliminated | Finance comparison | Management |
| Companies served without a code change | 1 | ≥ 3 onboarded through administration | Platform admin audit | Project owner |

## 10. Risks and assumptions (canonical risk register)
| Risk / assumption | Mitigation / note | Owner |
|---|---|---|
| Identity migration breaks existing training records | `docs/migration-h1.5.md` mapping and rehearsal; no production data yet | Tech authority |
| Cross-company data leak through an unscoped query, cache, task, export or storage key | Tenant filter in services/selectors, composite FKs, isolation + architecture tests, per-company cache and storage prefixes | Tech authority |
| Permission model becomes too coarse or too complex | One catalogue and matrix in `docs/access-control.md`; no ad-hoc checks; escalation tests | Project owner |
| Local account data raises privacy obligations | Minimal PII, retention, export/anonymization, legal review before go-live (`docs/security.md`) | Management + legal |
| Scope grows faster than delivery | H1.5 boundary above; new work needs an owner-approved requirement and task | Project owner |
| Hub contract or availability changes | Hub dormant and optional; adapters and contract tests; reactivation gate | Project owner + Hub owner |
| Video storage/bandwidth cost growth | Rendition policy; storage adapter; production provider decision D-001 | Project owner |
| Clients bypass skip protection | Server-authoritative heartbeat (REQ-09); abuse counter and report comparison | Tech authority |
| Accessibility/mobile found late | Mobile-first from the first screen; 320/390/768/1024/1440/1920 checks and axe in T-029/T-030/T-031/T-034 | Tech authority |
| Base-image vulnerabilities block CI | Time-boxed owner-approved exception process (`RULES.md` → Exceptions) | Project owner |
| Operator error on a shared host destroys another stack | Isolation table and prohibitions in `docs/operations/environments.md`; project-scoped commands only | Tech authority |
| A change silently drops a previously approved capability | Capability-preservation matrix in `docs/traceability.md`; no removal without an explicit owner decision; regression evidence before GATE-1 | Project owner |

## 11. Change control
Charter changes only when (a) the project owner asks, or (b) a blocking contradiction is found.
Procedure: a `[Decision]` or `[CHARTER CHANGE]` entry in `LOG.md` (what, why, who approved) →
edit this file → bump the version → propagate to `ARCHITECTURE.md`, `STATUS.md` and the owning
documents listed in `RULES.md` → document sync table. No document may keep a superseded scope
silently.

## 12. Approval
| Role | Name | Decision | Date |
|---|---|---|---|
| Project owner | (owner) | Approved | 2026-11-22 |
| Project owner | (owner) | Approved charter 2.3: H1 target — dual-mode access, `grants_only`, Academy-owned navigation | 2026-11-23 |
| Project owner | (owner) | Approved charter 2.4: standalone multi-company H1.5, local identity, dynamic scoped RBAC, public site, Hub dormant (D-031…D-040) | 2026-11-25 |
| Project owner | (owner) | Approved charter 2.5: one company membership per account, no company selection/switching, mobile-first and binding visual reference (D-043, D-044) | 2026-11-25 |
