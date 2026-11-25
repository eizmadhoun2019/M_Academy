# TRACEABILITY — IDs, Sources of Truth and Gates

**Status:** Canonical reference. Kept current by every task that closes
(`docs/skills/closing.md`).
**Last updated:** 2026-11-25

## 1. Identifier scheme

| Prefix | Meaning | Canonical location |
|---|---|---|
| `REQ-NN` | Charter requirement with acceptance criteria | `CHARTER.md` §5 |
| `T-NNN` | Build task (definition, dependencies, checkpoints) | `docs/plan.md`; state in `STATUS.md` |
| `GATE-N` | Phase gate | `docs/plan.md` §5, state in `STATUS.md` |
| `D-NNN` | Decision (open, defaulted, confirmed, superseded) | `docs/decisions.md` |
| `ADR-NNN` | Architecture decision record | `ARCHITECTURE.md` §12, `docs/adr/` |
| `EXCEPTION-<id>` | Approved deviation from an enforcement mechanism | `docs/exceptions/` |
| `G1`–`G12` | CI/quality gates | §3 below (normative) |
| `P1`–`P5`, `L1`–`L4`, `N1`–`N8`, `S1`–`S2`, `X1`–`X6` | Screen IDs | `docs/ui/screen-specification.md` |

**Rules:** tasks use `T-NNN`; decision numbers are never reused; retired legacy plan numbers
(`P0-NN`/`P1-NN`) and retired decisions (`D-018`…`D-022`) appear only in mapping tables. ADR numbers 15–22 are reserved legacy numbers and are never reused.

## 2. Legacy plan IDs → current tasks
| Legacy | Current | Scope |
|---|---|---|
| P0-13 | T-013, T-029 | UI foundation, then public/app shell |
| P0-15 | T-015, T-033 | Hub HTTP integration, then quarantine |
| P1-05 | T-019 | Assignments, auto-enroll, gating |
| P1-12 | **T-031** | Learner and management web UI |
| P1-19 | **T-034** | Load test at design capacity |
| P1-22 | **T-034** | Pilot and manager survey |
| P1-24 | T-016, T-028 | Permission grants, then scoped RBAC |

## 3. Quality gates
**Activation.** A gate is fully applicable from the task that first creates what it measures.
Until then it runs and reports its state explicitly: an inactive gate exits 0 **with a printed
reason**, so green never hides “not run”. This table is the single place that records which
gates are live; the task that activates a gate updates it.

| Gate | Check | Active | Fails the merge when |
|---|---|---|---|
| G1 | `ruff format --check` + `ruff check` | T-001 | Any finding |
| G2 | `mypy` (public functions typed) | T-001 | Any error |
| G3 | `pytest` with coverage over **all business-logic packages** (`academy/` excluding migrations, tests, settings) | T-001; expanded coverage from T-026 | Any failure, or coverage < 85% in an included package; only `services/selectors` is no longer sufficient |
| G4 | `makemigrations --check --dry-run` + migrate forward/back | T-001 | Missing or non-reversible migration |
| G5 | OpenAPI schema build | T-001 | Any warning |
| G6 | Security scans: `bandit`, `pip-audit`, image scan, `check --deploy` | T-001 | Any unresolved high/critical finding without an approved exception |
| G7 | Import boundary + tenant isolation + architecture rules | T-010 | `academy` imports host/`host_stub`/provider SDK; a cross-company leak; an unpermissioned route |
| G8 | Journey E2E + axe + visual regression | T-034 (`tests/e2e/` non-empty; a guard job decides) | Journey failure, axe critical/serious violation, or a visual mismatch against an approved reference without a recorded waiver |
| G9 | Documentation check (links, IDs, required sections, retired identifiers) | T-001 | Broken reference, missing section, or a retired ID in force |
| G10 | Identity/authorization matrix: catalogue integrity, role×route allow/deny, escalation, last admin, tenant scope, single membership, no company switch | **T-028** | Any matrix failure, missing catalogue row, second membership, or client-selected company accepted |
| G11 | Performance/load: design profile, API p95, heartbeat p95, query plans | **T-034** | Target missed without an owner-accepted deviation |
| G12 | Operational readiness: staging deploy, restore drill, alert drill, metrics/health | **T-034** | Missing or failed evidence |

G8, G10, G11 and G12 exit 0 with `inactive: <reason>` until their activation task lands. The CI
job records the reason in its log; the closing task flips the table and proves the gate can fail.

## 4. Requirement → task → evidence
| REQ | Task(s) | Evidence location |
|---|---|---|
| REQ-01 | T-001 | CI run on the merge commit; `/healthz` 200 |
| REQ-02 | T-004 | Four adapter contract suites |
| REQ-03 | T-006, T-007, T-008, T-010, **T-026** | Migration apply/reverse; composite-FK tests; isolation suite over every tenant table |
| REQ-04 | T-005, T-012, **T-026** | On-commit tests; trigger blocks UPDATE/DELETE; platform audit rows |
| REQ-05 | T-013, **T-029**, T-035 | Mobile-first render at 320/390/768/1024/1440/1920 in ar/en; axe report; no unjustified page-level overflow; approved reference or recorded waiver |
| REQ-06 | T-017, **T-031** | Publish validation + immutability tests; authoring journey |
| REQ-07 | T-018, **T-031** | Media pipeline integration test; playback UI + presigned URL test |
| REQ-08 | T-019, **T-026** | Assignment matrix; auto-enroll after membership change |
| REQ-09 | T-020, **T-031** | Progress matrix (`docs/domain-model.md` §7); UI journey |
| REQ-10, REQ-11 | T-021, **T-032** | Frozen-time idempotency tests; per-company time zone; rendered mail |
| REQ-12 | T-022, **T-032** | Query-count/scope tests; platform aggregate; CSV formula-safe |
| REQ-13 | T-016, **T-028** | Role×permission×scope matrix; escalation and last-admin tests |
| REQ-14 | **T-031** (was T-023) | Playwright journey + manual check record in LOG |
| REQ-15 | **T-034** | E2E ar/en at 320/390/768/1024/1440/1920; axe zero critical/serious; visual regression against approved implemented baselines |
| REQ-16 | **T-034** | Staging deploy, restore transcript, alert drill |
| REQ-17 | **T-034** | Locust report against D-042 profile |
| REQ-18 | **T-034** | ASVS L1 checklist; scan outputs; CSP/header verification |
| REQ-19 | **T-027**, **T-028**, **T-034** | Privacy export/anonymization tests; PII registry check |
| REQ-20 | **T-034** | Pilot notes and triage |
| REQ-21 | **T-026** | Organization/membership/department tests; `UNIQUE (user_id)`; isolation; duplicate-membership migration abort; platform accounts without membership |
| REQ-22 | **T-027** | Auth/MFA/session matrix; production dev-login guard; log-secret grep |
| REQ-23 | **T-028** | G10 matrix; catalogue integrity; last-admin |
| REQ-24 | **T-029** | Public/app route tests; no-session render; direct post-login routing; no company chooser; language switch |
| REQ-25 | **T-030** | Company/platform administration integration tests; explicit platform company id; no synthetic membership; audit samples |
| REQ-26 | **T-027**, **T-032**, **T-033** | SMTP transcript; no Hub call when disabled |
| REQ-27 | **T-034** | Metrics/health/alerts evidence; slow-query log |
| REQ-28 | **T-026**, **T-027**, **T-028**, **T-034** | Migration reconciliation; legacy mapping; compatibility test |

Every requirement has at least one task and one evidence type. A task without a requirement is a
plan defect; a requirement without a task is a gate blocker.

### 4.1 Capability-preservation matrix (H1.5 transition)
This is the regression contract for «الحفاظ على الوظائف السابقة». One company membership per
account changes **who** supplies the company context, not **what** the platform can do. No row may
be removed or weakened without an explicit owner decision in `docs/decisions.md`; T-034 verifies
every row against the new tenancy/RBAC model before GATE-1.

| Capability (approved before H1.5) | Prior source | H1.5 mechanism | Task | Regression evidence |
|---|---|---|---|---|
| Create/edit courses, content and media | REQ-06, T-017/T-018 | `academy.content.*` / `academy.media.manage` at COMPANY or DEPARTMENT scope | T-028, T-031 | Authoring journey + media integration tests |
| Publish, archive and immutable published versions | REQ-06, T-017 | Publish service + frozen versions, permission-gated | T-031, T-034 | Publish/immutability tests and UI journey |
| Department head creates/edits/publishes/archives within scope | REQ-06, REQ-13 | Department-scoped content permissions and object checks | T-028, T-031 | Department scope matrix |
| Assign a specific employee | REQ-08, T-019 | `Assignment.target_type=membership` in the same company | T-026, T-031 | Assignment matrix |
| Assign a whole department | REQ-08, T-019 | `target_type=department` with tenant FK | T-026, T-031 | Assignment matrix and isolation |
| Assign by job role | REQ-08, T-019 | `target_type=role` resolved to active memberships | T-028, T-031 | Role-target matrix |
| Assign the whole company | REQ-08, D-015 | `target_type=organization`, requires company-scope assignment permission | T-026, T-031 | Company-target test |
| Mandatory / optional training | REQ-08 | `Assignment.mandatory` unchanged | T-031 | Report + learner UI states |
| Due dates and overdue states | REQ-08/REQ-10 | `due_at`, company time zone | T-031, T-032 | Frozen-clock tests |
| Auto-enrol new employees matching an assignment | REQ-08, D-015 | Trigger on membership activation; assignment targets re-evaluated in the same company | T-026, T-034 | Auto-enrol after membership change |
| Preview recipients before assignment | REQ-08, D-017 | Recipient preview selector, scoped to the company | T-031 | Preview count/roster test |
| Prevent duplicate enrolment | REQ-08 | Partial unique index per membership/course | T-026, T-034 | Idempotent assignment test |
| Sequential learning, anti-skip and completion threshold | REQ-09, T-020 | Server heartbeat/progress rules unchanged; company derived from membership | T-031, T-034 | Progress matrix |
| Learner dashboard, courses and achievements | REQ-14, T-023→T-031 | L1–L4/E with SELF scope | T-031 | Playwright learner journey |
| Reminders, escalation and manager digest | REQ-10/11, T-021 | Recipients resolved through membership; per-company schedule and locale | T-032 | Frozen-clock and mail tests |
| In-app/email notifications | REQ-11, T-021 | Local recipients and dedupe keys preserved | T-032 | Notification delivery tests |
| Company reports and CSV export within scope | REQ-12, T-022 | Scoped selectors + formula-safe export; platform aggregate with explicit company | T-032 | Report scope and CSV tests |
| Additional grants for a specific user | REQ-13, T-016 | `PermissionGrant` on the single membership with reason/expiry | T-028 | Grant/revoke matrix |
| Audit trail and attribution | REQ-04, T-012 | `actor_user_id` + `actor_membership_id`; platform events nullable | T-026, T-028 | Append-only and audit assertions |
| Account, session, MFA and invitation lifecycle | REQ-22, T-014 | Local auth; one membership; invitation rejects second company | T-027 | Auth matrix + second-membership test |
| Company administration: users, invitations, departments, roles and settings | REQ-21, REQ-25, CHARTER G5 | Company Admin manages one company through scoped permissions; platform targets it by explicit id | T-026, T-027, T-028, T-030 | Administration scope matrix and isolation tests |
| Platform administration without a company row | REQ-25 | `PlatformRoleAssignment`; explicit company id; audited read-only access | T-028, T-030 | Platform permission/access tests |
| Public site and permission-aware navigation | REQ-24, T-013 | Public P1–P5; direct dashboard routing; dynamic sidebar | T-029 | Route/nav matrix |

## 5. Sources of truth (never restate elsewhere)
| Fact | Only canonical file |
|---|---|
| Vision, scope, requirements, success measures, product risks | `CHARTER.md` |
| Architecture, module boundaries, data/security placement, ADR summaries | `ARCHITECTURE.md` |
| Binding rules, «كمل» protocol, approvals, stop conditions, sync table | `RULES.md` |
| Decisions and their status/value | `docs/decisions.md` |
| Task definitions, dependencies, checkpoint criteria, gate composition | `docs/plan.md` |
| Current state, evidence, blockers, next action | `STATUS.md` |
| History | `LOG.md` |
| Permission catalogue, roles, scopes, enforcement, audit event names | `docs/access-control.md` |
| Security controls, PII register, retention, incident response | `docs/security.md` |
| Entities, fields, constraints, state machines, progress algorithm | `docs/domain-model.md` |
| API surface, error codes, compatibility | `docs/api.md` |
| Settings, upload policy, HLS, pagination, throttles, company settings | `docs/configuration.md` |
| Celery task names, schedules, retries, idempotency | `docs/background-jobs.md` |
| Report metrics, columns, CSV format | `docs/reports.md` |
| Notification/reminder copy (ar/en), channels, dedupe keys | `docs/notifications.md` |
| Screen requirements, navigation, UI states, mobile-first per-screen acceptance, visual gate | `docs/ui/screen-specification.md` |
| Identity, master shell, components, responsive rules, tokens, visual acceptance | `docs/ui/design-system.md`, `docs/ui/design-tokens.json` |
| Screen-group reference mapping and per-group approval record | `docs/ui/wireframes.md` |
| Design package provenance, reference fingerprints, archive and restore | `docs/ui/design-reference.md` |
| Hub ↔ Academy wire contract and activation state | `docs/hub-contract.md` |
| Migration mapping, cutover, rollback | `docs/migration-h1.5.md` |
| Repository identity, stack, ports, buckets, cookies, environments, deploy, backup, alerts | `docs/operations/environments.md` |
| NFR targets and capacity | `docs/performance-profile.yaml` (owned by CHARTER) |

## 6. Verification
```bash
python scripts/check_docs.py
grep -rn "P0-[0-9]\|P1-[0-9]" --include=*.md . | grep -v "traceability.md" | grep -v "decisions.md" || echo clean
grep -rn "T-0[0-9][0-9]" --include=*.md .   # every task exists in plan.md
```
`docs/traceability.md`, `docs/plan.md`, `STATUS.md` and `LOG.md` must agree: every `T-NNN` in
STATUS exists here and in the plan; every `REQ` maps to at least one task; no retired identifier
is in force. The consistency audit in T-034 repeats this manually plus the semantic review.
