# RULES — Masheed Academy

**Status:** Binding. Applies to humans and AI agents equally.
**Last reviewed:** 2026-11-25

## Authority
- **Project owner:** scope, priorities, open decisions, gate and release approval.
- **Technical authority:** lead developer / AI agent operator; routine execution inside this
  document's limits.
- **Security/privacy authority:** project owner + company legal advisor.
- **Release authority:** project owner.

## Precedence
Company legal/organizational obligations > `CHARTER.md` > `RULES.md` > approved decisions
(`docs/decisions.md`) and `ARCHITECTURE.md` > canonical specifications (`docs/domain-model.md`,
`docs/access-control.md`, `docs/security.md`, `docs/api.md`, `docs/ui/design-system.md`, …) >
`STATUS.md` / `docs/plan.md` >
`LOG.md` > `SKILLS.md`.

On conflict: stop the task, record the conflict in `STATUS.md` (open decisions) and `LOG.md`,
and ask the owner. Never keep two contradictory rules in force.

## Documentation-driven operation
The repository is the only operational source of truth. A new agent or developer must be able
to continue from these files alone, in this order:

1. `README.md` — what the project is and where everything lives.
2. `CHARTER.md` — vision, scope, requirements, risks.
3. `RULES.md` — binding rules (this file).
4. `ARCHITECTURE.md` — target design and current limits.
5. `docs/access-control.md` and `docs/security.md` — non-negotiable authorization and security.
6. `docs/plan.md` — task map, dependencies, acceptance criteria.
7. `STATUS.md` — what is true now and what comes next.
8. The canonical specification for the work at hand (`docs/domain-model.md`, `docs/api.md`,
   `docs/configuration.md`, `docs/ui/screen-specification.md`, …).
9. `docs/decisions.md` — only place where a deferred decision has a value.
10. `LOG.md` — history; read the last entries for context, never as current instructions.

Chat history, external UX packages and legacy repositories are **not** sources of authority.
A fact that is not in the repository does not exist for the agent.

## The «كمل» protocol
A bare «كمل» / «continue» is authorization to execute **the next eligible checkpoint** under the
approved plan. It is not a new scope and not permission to skip governance. On «كمل» the agent
must, automatically:

1. Read the project state: `STATUS.md`, then the active checkpoint in `docs/plan.md`.
2. Review the owning specification, the relevant decisions and the rules that apply.
3. Inspect the repository: branch, working tree, untracked files, recent commits, CI state.
4. Select the next task/checkpoint by **dependency order**, not by task number or preference.
5. Confirm it is approved, eligible and not `[!]` blocked; otherwise stop and report.
6. Create or reuse the task branch `task/<T-NNN>-<slug>` from up-to-date `main`.
7. Implement only that checkpoint's scope, applying the architecture, security, tenancy and
   authorization requirements.
8. Apply the applicable quality, i18n, accessibility and observability standards.
9. Add or update the tests the checkpoint requires; never weaken an existing test.
10. Run the gates active for that checkpoint locally; keep the real exit status. A check that
    could not run is reported, not assumed.
11. Review the diff for regressions, secrets, generated files and unrelated changes.
12. Update only the documents that own a changed fact (see the sync table).
13. Update `docs/traceability.md` when a requirement or evidence link changed, then `STATUS.md`
    (state, evidence, next action) and append one `LOG.md` entry.
14. Commit with a Conventional Commit subject ≤ 72 characters naming the task (`Refs: T-NNN`);
    push the task branch. Do not merge to `main` without the owner's approval.
15. Verify CI on the pushed commit and record the run as evidence; do not claim a gate that did
    not run.
16. Report concisely: what changed, evidence, checks, limitations, next checkpoint.
17. Stop at the end of the checkpoint. Do not start the next one without «كمل».

Rules for «كمل»:
- Do not ask the owner to restate approved requirements, architecture, security or design.
- Do not ask about routine implementation choices that the documents already settle; decide,
  implement, and record the choice if it is material.
- Routine execution decisions inside the approved scope may be taken by the agent. Decisions
  that change scope, architecture, an interface, security/privacy, cost or data require the
  owner (see stop conditions).
- «كمل» never overrides an approval gate, a CI gate, a security control or a data-loss
  prohibition.
- If a checkpoint is too large to finish safely, split it in `docs/plan.md` first (same task,
  explicit checkpoints CP1/CP2…), complete CP1, and say which checkpoint comes next.

## Mandatory working rules
- **One checkpoint, one branch, one focused change.** Task IDs come from `docs/plan.md`;
  branches `task/<T-NNN>-<slug>`.
- Stay inside the approved scope. Out-of-scope work becomes a proposed plan row awaiting an
  owner-assigned requirement.
- **Tenant rule:** every tenant model has an `organization` FK; every runtime query goes through
  a manager/selector scoped by the derived company; a task, cache key, storage key, export and
  audit row carries the company. No unscoped default-manager read in runtime code.
- **Identity rule:** users are identified by UUID (`User`), never by email. Business rows point
  at `Membership`, not at a raw ref string. Email is a login attribute only.
- **Permission rule:** every view/route/action declares a permission and its allowed scopes; the
  service rechecks company and scope; deny by default. No ad-hoc `is_admin` checks.
- Business logic lives only in services; reads in selectors; views/serializers/tasks/hooks thin.
- Writes inside `transaction.atomic()`; side effects via domain events on commit; services raise
  domain exceptions, never return error codes.
- Type hints on public functions; `ruff` and `mypy` clean; time via `timezone.now()`.
- Every state-changing administrative action and every denied authorization attempt records an
  `AuditEvent` in the same transaction. Never update or delete audit rows.
- No secrets, tokens, password material or unnecessary personal data in the repository, tests,
  logs, seeds or error messages. Account email is the only stored personal identifier; see
  `docs/security.md` §6.
- Do not claim completion without evidence. Documents describe reality before a task closes.
- No orphan TODO: `# TODO(T-031): ...` with a task ID from `docs/plan.md`.
- **Own repository and own runtime.** No file, image, volume, database, bucket or credential is
  copied from the legacy project; the legacy stack is never stopped or modified. Compose
  commands always carry `-p m-academy`; destructive Docker commands are prohibited.
- Cookie names are namespaced (`m_academy_sessionid`, `academy_csrftoken`).

## Change approval
| Change type | Required approver |
|---|---|
| Scope, requirements, acceptance criteria (`CHARTER.md`) | Project owner |
| Architecture boundary, tenancy model, identity model, permission model | Project owner |
| A public API or data contract change that is not backward compatible | Project owner |
| New dependency, external service or paid resource | Technical authority + security scan; owner when it creates cost or a vendor commitment |
| Production deploy, publish, phase gate, merge to `main` | Project owner |
| Mandatory-requirement exception | Project owner, recorded per Exceptions |
| Removing or weakening an approved capability, or changing an approved screen design/identity | Project owner, recorded in `docs/decisions.md` and the capability matrix |

## Task lifecycle
`[ ]` todo · `[~]` in progress/review (owner, date) · `[!]` blocked (reason) · `[x]` done on
`main` with merge commit + CI evidence · `[–]` superseded (successor named).

A phase gate closes only when every task in the gate and its acceptance criteria are verified.
Reopening a completed task requires a recorded reason in `STATUS.md` and `LOG.md`.

**Capability preservation:** one company membership per account is an H1.5 architectural constraint,
not a reduction of training functions. No capability approved before H1.5 (authoring/publishing,
department-head authoring, assignment to member/department/role/company, mandatory/optional,
due dates, auto-enrolment, recipient preview, duplicate prevention, progress/completion,
reminders/escalation, scoped reports/export, exceptional grants and learning rules) may be
removed or weakened without an explicit owner decision. `docs/traceability.md` carries the
capability matrix that must be verified at GATE-1.

`LOG.md` status values (event states): Proposed | Approved | Implemented | Tested | Verified |
Merged | Released | Rejected | Superseded. Implemented, Tested, Verified, Merged and Released
require evidence.

## Quality gates
Definitions, activation and current state: `docs/traceability.md` §3. Summary:
G1 format/lint · G2 types · G3 tests with coverage on **all business-logic packages** · G4
migrations · G5 OpenAPI · G6 security scans · G7 architecture + tenant isolation · G8 E2E +
accessibility · G9 documentation · G10 identity/authorization matrix · G11 performance/load ·
G12 operational readiness.

A failed gate is never bypassed, skipped or silenced. Use the Exceptions mechanism. A gate that
is not applicable yet exits 0 **with a printed reason**, so green never hides “not run”.

## Document sync table
A task that changes a fact updates the owning document in the same commit. `docs/skills/closing.md`
refers to this table.

| When this changes | Update |
|---|---|
| Vision, scope, requirements, success measures, product risks | `CHARTER.md` (+ LOG) |
| Architecture, module boundary, data strategy, ADR | `ARCHITECTURE.md` §12, `docs/adr/` |
| A decision's value or status | `docs/decisions.md`, then every document that quotes it |
| Task state, current phase, blockers, next action | `STATUS.md` |
| Task definitions, dependencies, checkpoints, gate composition | `docs/plan.md` |
| Completed or approved work | `LOG.md` (append-only) |
| IDs, gates, requirement coverage, capability preservation, sources of truth | `docs/traceability.md` |
| Permission catalogue, roles, scopes, enforcement | `docs/access-control.md` (+ tests) |
| Security control, PII field, retention, session policy | `docs/security.md` |
| Schema, constraints, integrity, state machines, progress algorithm | `docs/domain-model.md` |
| Endpoint, auth flow, error code, compatibility | `docs/api.md` |
| Setting, default, upload policy, HLS, pagination, throttle | `docs/configuration.md` |
| Background job, schedule, retry, idempotency | `docs/background-jobs.md` |
| Report metric, column, CSV format | `docs/reports.md` |
| Notification copy, channel, locale, link | `docs/notifications.md` |
| Identity, master shell, components, responsive rules, design tokens, visual acceptance | `docs/ui/design-system.md`, `docs/ui/design-tokens.json` |
| Screen, navigation, UI state, mobile-first per-screen acceptance, visual gate | `docs/ui/screen-specification.md` |
| Screen-group reference mapping and gate status | `docs/ui/wireframes.md` |
| Design package provenance, reference fingerprints, archive and restore | `docs/ui/design-reference.md` |
| Ports, containers, buckets, environments, deploy, backup, alerts | `docs/operations/environments.md` |
| Migration mapping, cutover, rollback | `docs/migration-h1.5.md` |
| Hub wire contract, activation state | `docs/hub-contract.md` |

## Definition of done
A task is `[x]` only when:
1. Every acceptance criterion in its `docs/plan.md` card has cited evidence: file+line, test name
   or command output.
2. The gates active for it pass on the merge commit; none is bypassed, skipped or silenced.
3. The owning documents are updated and `python scripts/check_docs.py` passes.
4. `ruff`, `mypy`, the migration check and the tests covering the change pass locally.
5. `LOG.md` has one entry with evidence. `STATUS.md` cites the latest **content** commit SHA and
   the CI run for that commit. A trailing evidence-only commit may update those citations without
   citing its own SHA; the closing report names the final branch head and CI run. Never amend a
   content commit to embed its own hash, and never claim CI for a commit that has not run it.
6. No orphan TODO and no superseded statement left in force.

## Commit messages
Conventional Commits, one focused change per commit, English imperative subject ≤ 72
characters: `<type>(<scope>): <subject>`. Types: `feat`, `fix`, `docs`, `refactor`, `test`,
`build`, `ci`, `chore`, `perf`. The body says why and names the task (`Refs: T-025`). Never
commit secrets, `.env`, generated artifacts or unrelated files.

## UI and frontend rules
- **Single design source:** `docs/ui/design-system.md` and `docs/ui/design-tokens.json` are the
  only visual authority; `R05-master` governs every internal screen. One Master Base Layout
  (charcoal sidebar, white header, light canvas, white cards, restrained gold) serves every
  authorized role. No role-specific or page-specific shell, no photographic banner inside the
  application; public and auth screens keep the approved architectural imagery. A second design
  package, wireframe set or token file may not enter the repository without a decision.
- Strict CSP without `unsafe-inline`: no inline `style=` and no inline `<script>`; styles and
  scripts ship as cacheable files.
- RTL first: logical properties (`margin-inline-start`, `padding-block`, `inset-inline-start`).
- Every user-visible string comes from gettext (`ar` default RTL, `en` secondary); no literal
  copy in templates or scripts.
- Brand: locally hosted **Rubik** (Arabic + Latin), Primary `#101820`, Brand Gold `#E8AA23`,
  Canvas `#F5F7FA`, Surface `#FFFFFF`, and the official Masheed logo and gold geometric element
  from the approved package. Do not invent or redraw the mark, and do not declare a substitute
  font approved; until the assets are supplied, use the text placeholder and record the gap.
- **Mobile first is binding:** every screen is designed and built Mobile 390 → Tablet 768 →
  Desktop 1440 → Large Desktop, never the reverse. Verify 320, 390, 768, 1024, 1440 and 1920 px in
  Arabic RTL and English LTR: no unjustified page-level horizontal scroll, tables become labelled
  cards or scroll only inside their own container, dialogs stay in the viewport, core functions
  survive on mobile, and desktop-first shrinking is prohibited.
- WCAG 2.2 AA: labelled controls, visible focus, keyboard-reachable controls, 44×44 px targets,
  no colour-only meaning, no raw UUID shown when a name exists, 200 % zoom and reduced motion.
- **Components, not copies:** build on the shared app shell, partials and component patterns with
  central tokens; no duplicated component variant per page and no ad-hoc visual values. No new UI,
  CSS or JavaScript library and no build step without owner approval.
- **Visual-reference gate:** a screen group is implemented only after its reference and the
  owner's approval (or an explicit waiver) are recorded in `docs/ui/wireframes.md`; approved
  designs are binding and are not redesigned or rearranged without owner approval. Visual
  regression compares rendered screens with an approved **implemented** baseline at the six
  verification widths — never a pixel comparison against generated boards. Similarity to a mockup
  is not a visual pass.
- **Design assets stay out of Git:** packages, boards and PDFs live outside the repository
  (`../_design-archive/`) or in the Git-ignored `.design-references/`; only text specifications and
  tokens are tracked. Never publish mockups, portraits or unlicensed assets to the public remote.
- Every screen implements the state contract in `docs/ui/screen-specification.md` §5; never show
  success before the server confirms it.

## Dependencies
- Every dependency is pinned to an exact version in `pyproject.toml`; no floating ranges.
- A new dependency or external service needs technical-authority approval and a clean
  `pip-audit` in the same change. Security-sensitive libraries (MFA, crypto) additionally need
  an owner-visible rationale and a maintained-release check.
- Upgrading or removing a pinned version is a normal change; the reason goes in the commit body.
- Provider SDKs never appear inside `academy/`; adapters own them.

## AI agent permissions
- **Allowed:** implement approved checkpoints end-to-end; run focused verification; update the
  documents that own a changed fact; push task branches; append `LOG.md`; run read-only
  diagnosis of this project's stack.
- **Prohibited:** bypassing or disabling a gate; changing scope or acceptance criteria; merging
  to `main` without owner instruction; deploying to production; storing personal data or
  secrets; rewriting `LOG.md` history; enabling Hub or another integration without a decision;
  modifying the legacy stack.
- **Prohibited environment actions:** `docker system prune`, `docker volume prune`,
  `docker network prune`, `docker rm -f`, `docker image prune -a`, `docker compose down`
  without `-p m-academy`, and stopping/restarting/inspecting-modifying any other project's
  containers.
- **Prohibited:** changing repository visibility or pushing to a new remote without owner
  authorization (D-023).

## Stop conditions
Stop and ask the owner (record in `STATUS.md` and `LOG.md`) when:
- scope, an architectural boundary, the tenancy/identity/permission model, or an interface
  contract would change;
- a security or privacy decision is not already settled by `docs/security.md` or a decision;
- data could be lost, or a destructive/production action is required;
- money, an external account, a paid service or unavailable credentials are required;
- two approved documents genuinely conflict and the precedence order does not settle it;
- a blocker prevents correct execution (missing service, failing CI outside the task, missing
  access);
- the next planned checkpoint is unapproved or depends on an unapproved one.

When asking: give the options, the trade-offs, the recommendation and the impact. Do not ask
questions the repository can answer.

## Exceptions
An exception record states: justification, risk, compensating controls, a verifiable removal
condition and verifier, approver, review/expiry date. Model:
`docs/exceptions/EXCEPTION-<id>.yaml`.
- A change to an enforcement mechanism (gate, check, policy) is its own task; if it cannot pass
  the gate it modifies, an approved exception must exist before integration and be logged.
- Exceptions never renew automatically; renewal needs a new approval record.
- Enforce expiry mechanically where feasible.
