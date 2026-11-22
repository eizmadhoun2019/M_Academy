# CHARTER — Project Purpose, Scope and Success

**Charter version:** 2.2 (UPDS baseline; supersedes legacy charter 1.3 content, same scope;
2.1 corrected decision IDs to `docs/decisions.md`; 2.2 adds the new-repository and
isolated-environment constraints — no change to product scope)
**Approved by:** Project owner
**Last reviewed:** 2026-11-22

## 1. Identity and purpose
- **Project name:** Masheed_Academy (Python package: `academy`).
- **Purpose:** One central, automated, trackable place to train employees — every employee
  receives the same quality of onboarding and mandatory training, managers know exactly who
  completed what and when, and nobody chases people manually.
- **Problem:** Ad-hoc training wastes time and causes errors; managers cannot see completion;
  manual reminders consume management time; external LMS platforms mean per-seat recurring
  cost and training data leaving our systems.
- **Vision (three horizons):** H1 internal module inside Masheed Hub (this charter) ·
  H2 sellable add-on for Hub customers (multi-tenancy, plans, white-label) ·
  H3 standalone platform (own SSO, SCORM/xAPI, AI). This charter authorizes H1 with an
  architecture that does not block H2/H3.

## 2. Goals
- G1 Deliver video-based courses through the account employees already use.
- G2 Enforce sequential learning with server-verified progress (the browser is never trusted).
- G3 Automate assignment, reminders, escalation and completion notifications.
- G4 Give managers a dashboard and CSV export of completion status.
- G5 Build a modular foundation (adapters, events, tenant scoping, API-first) detachable for productization.

## 3. Users and stakeholders
| Group | Role in the product |
|---|---|
| Employees (`employee` Hub role) | Learners; enrollments, resume, locked sequential lessons. |
| Department managers | Author/assign within their departments; view scoped reports. |
| Platform administrators | Full organization access; permission grants, audit, settings. |
| HR staff (via grants) | May receive capabilities (assign, reports) without a Hub role change. |
| Masheed Hub team | Owns sign-in, reverse proxy `/academy/*`, signed identity, webhooks. |
| Project owner / management | Sponsor; approves scope, decisions D-001… and UAT. |

## 4. Scope
### In scope (H1)
- Course authoring with immutable versions, sections, lessons (video Phase 1; pdf/text Phase 2).
- Media upload + HLS processing (360p/720p, 6 s segments), optional WebVTT captions.
- Assignment to user/department/role, due dates, mandatory flag, auto-enroll on join.
- Server-authoritative heartbeat progress, anti-skip, completion records.
- Notifications (learner + manager), reminders with manager escalation digest.
- Reports + CSV export; Academy-managed permission grants; audit trail.
- Privacy: export, anonymization, retention; Arabic (RTL) and English UI, WCAG 2.2 AA.
### Out of scope (H1)
Live streaming, comments/forums, gamification, SCORM/xAPI, payments, mobile apps, AI,
certificates (Phase 2), quizzes UI (Phase 2 — schema only in Phase 1), custom branding (Phase 3).

## 5. Requirements
Requirement IDs are stable; acceptance criteria are verified by automated tests or recorded
manual checks in LOG.md before release.

| ID | Requirement | Priority | Acceptance criteria | Owner |
|---|---|---|---|---|
| REQ-01 | Foundation scaffold and CI quality gates | Must | Clean checkout runs via compose; lint/type/tests/docs gates green in CI | Tech authority |
| REQ-02 | Adapter layer + host stub with contract suites | Must | 4 adapter contracts (identity, org, notify, storage) pass for stub and Hub HTTP fakes | Tech authority |
| REQ-03 | Full Phase 0–2 schema with migrations | Must | All models are tenant-scoped; migrations apply/reverse; tenant-isolation suite passes | Tech authority |
| REQ-04 | Domain events on commit + audit trail (append-only) | Must | Events fire only after commit; audit rows immutable at DB level | Tech authority |
| REQ-05 | Bilingual RTL/LTR UI foundation per visual baseline | Must | Tokens, shell, wireframes committed; renders at 360/768/1280 px in ar+en | Tech authority |
| REQ-06 | Course authoring, versions, publish | Must | ≥2 sections/lessons, publish validation, immutability, prior version archived | Tech authority |
| REQ-07 | Media upload → HLS processing → secure playback | Must | Upload via presigned PUT; ffmpeg→HLS `ready`; failures retryable; learner-only playback | Tech authority |
| REQ-08 | Assignment + auto-enroll on join | Must | User/dept/role targets, due date, mandatory flag; `member_changed` auto-enrollment | Tech authority |
| REQ-09 | Sequential locking + server-verified progress | Must | Lesson N+1 locked until N complete; forward skip rejected by server; ≥90% watched completes | Tech authority |
| REQ-10 | Completion + notifications exactly once | Must | Learner congrats + manager notification, idempotent via NotificationLog | Tech authority |
| REQ-11 | Reminders + escalation | Must | due−3/due/due+1 learner reminders; manager digest at due+3; idempotent (ReminderLog) | Tech authority |
| REQ-12 | Manager reports + CSV | Must | Completion %, overdue, avg time per course/department; formula-safe CSV; scoped | Tech authority |
| REQ-13 | Permission grants | Must | Allow/deny/scope matrix for role defaults + grants, both modes, DRF and web; last-admin protection; audited | Project owner |
| REQ-14 | Learner + management web UI | Must | My courses, outline/locks, player (hls.js) + resume; editor, uploader, assignments, dashboard | Tech authority |
| REQ-15 | Journey/E2E, accessibility, responsiveness | Must | Full API journey test; Playwright at 3 viewports in ar+en; axe zero critical/serious | Tech authority |
| REQ-16 | Operations | Must | Staging deploy from CI; daily backup; recorded restore drill; monitored /healthz with alerts | Tech authority |
| REQ-17 | Performance at design capacity | Must | §6 targets met in load test or owner-accepted deviation recorded | Project owner |
| REQ-18 | Security review | Must | OWASP ASVS L1 checklist complete; dependency + image scans clean | Tech authority |
| REQ-19 | Privacy tooling | Must | `export_user_data` / `anonymize_user` tested; retention configurable; meta-test covers all `user_ref` models | Project owner |
| REQ-20 | Pilot + management demo | Must | Pilot group completes a real course; feedback recorded and triaged | Project owner |

## 6. Non-functional requirements
Full targets live in `docs/performance-profile.yaml` (CHARTER owns them). Summary:
capacity 1,000 learners / 200 concurrent viewers / 20 admins / 100 courses; API p95 < 300 ms
(heartbeat p95 < 150 ms); LCP ≤ 2.5 s, INP ≤ 200 ms on mid-range phone over 4G; availability
99.5% monthly; RPO ≤ 24 h, RTO ≤ 4 h; OWASP ASVS L1 + WCAG 2.2 AA; latest-2 versions of
Chrome/Edge/Firefox/Safari/Samsung Internet; ar (default, RTL) + en; ≥85% coverage on
services/selectors.

## 7. Project profile
### Scale
**Medium.**

**Rationale and indicators:** single organization now (schema multi-tenant from day one),
≈1,000 learners, 200 concurrent video viewers, ~14 heartbeat req/s, two-server topology
(Hub + Academy), 4 adapters, background workers, Arabic/English UI with accessibility
obligations.

### Sensitivity
**Sensitive.**

**Rationale:** employee training data and behavioral progress under employee-monitoring
rules; opaque `user_ref` only (ADR: privacy by minimization); signed identity and webhooks
cross a trust boundary between two servers; append-only audit.

### Performance profile
Canonical location: `docs/performance-profile.yaml` (approved with this charter).

## 8. Constraints and dependencies
- Hub integration contract is **proposed** — Hub-team confirmation pending (identity format
  D-004, Hub implementation D-010, domain/TLS D-005, menu source D-011, ingress D-012; the
  single register is `docs/decisions.md`).
- Business time zone (D-002), retention periods (D-003), browser support (D-007), brand
  font/wordmark (D-008) and video storage provider (D-001) use the defaults recorded in
  `docs/decisions.md` until the owner decides; none of them blocks the build.
- 12-factor config; one image promoted across environments.
- **New repository, no legacy dependency.** The rebuild lives in its own repository
  (`M_Academy`) with its own history. The legacy repository and its deployment keep running
  unchanged and are reference-only: no code, config, image, volume, database, cache or
  credential is carried over.
- **Isolated runtime.** The new stack owns its containers, PostgreSQL instance, Redis
  instance, object storage and buckets, Celery broker and secrets, on its own ports and
  network. It must be able to run side by side with the legacy stack on the same host
  without sharing or disturbing anything (`docs/operations/environments.md`).

## 9. Success measures
| Measure | Baseline | Target | Measurement method | Owner |
|---|---|---|---|---|
| Mandatory-course completion within 30 days of assignment | TBD (owner, before pilot) | ≥ 90% | Reports query per course | Project owner |
| Manager time on training follow-up | TBD | reduced by [X] hours/month | Manager survey (pilot, T-024) | Project owner |
| New hires with onboarding complete within 2 weeks | TBD | ≥ [X]% | Reports query | Project owner |
| External LMS subscription cost for covered use cases | current spend | eliminated | Finance comparison | Management |

## 10. Risks and assumptions
| Risk / assumption | Mitigation / note |
|---|---|
| Hub's real identity/org model differs from assumptions | Contract tests with HTTP fakes; open decisions D-004, D-005, D-010…D-012 |
| Video storage/bandwidth cost growth | Renditions policy; storage adapter seam; D-001 |
| Clients bypass skip protection | Server-authoritative heartbeat (REQ-09); abuse tests |
| Module entangles with Hub | Import-boundary test; adapters are the only seams |
| Accessibility/mobile found late | UI foundation early; axe in E2E (REQ-15) |
| Employee-privacy/legal concerns | Retention and legal basis (D-003) confirmed with legal advisor before go-live; REQ-19 |
| Base-image vulnerabilities block CI | Time-boxed owner-approved exception process (RULES → Exceptions) |

## 11. Change control
Charter changes only when (a) the project owner asks, or (b) a blocking contradiction is
found. Procedure: `[Decision]` entry in LOG.md (what, why, who approved) → edit this file →
bump version → propagate to ARCHITECTURE/STATUS.

## 12. Approval
| Role | Name | Decision | Date |
|---|---|---|---|
| Project owner | (owner) | Approved | 2026-11-22 |
