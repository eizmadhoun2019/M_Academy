# RULES — Masheed_Academy

## Authority
- Project owner: (owner) — scope, priorities, open decisions, UAT acceptance.
- Technical authority: lead developer / AI agent operator.
- Security/privacy authority: project owner + company legal advisor (employee data).
- Release authority: project owner.

## Precedence
Company legal/organizational obligations > CHARTER > RULES > approved decisions /
ARCHITECTURE > STATUS/LOG > SKILLS. On conflict: stop the task, record it in LOG.md and
STATUS.md open decisions, and ask the project owner.

## Mandatory working rules
- **One task, one branch, one focused change.** Task IDs come from STATUS.md; branches `task/<ID>-<slug>`.
- Stay within approved scope; out-of-scope work becomes a proposed row awaiting an owner-assigned ID.
- The `academy/` package never imports the host or `host_stub`; users are opaque `user_ref`
  strings (no user-model FK); every tenant query goes through `for_org(organization_id)`.
- Business logic lives only in `services/`; reads in `selectors/`; views/serializers/tasks/hooks thin.
- Writes in `transaction.atomic()`; side effects via domain events on commit; services raise
  domain exceptions, never return error codes.
- Type hints on public functions; `ruff` + `mypy` clean; time only via `timezone.now()`.
- Every state-changing admin operation and every denied admin action records an `AuditEvent`
  in the same transaction. Never update/delete audit rows.
- No secrets, PII, or host-owned personal data (names/emails) in repo, tests, logs or seeds.
- Do not claim completion without evidence; documents must reflect reality before a task closes.
- No orphan TODOs: `# TODO(T-020): ...` with a task ID from STATUS.
- **Own repository only.** The project lives in its own repository (`M_Academy`) with its own
  history. Nothing is copied from the legacy implementation: if a legacy file is consulted,
  it is re-derived from these documents and re-implemented here. Legacy commits, tags,
  images, volumes and credentials are never imported.
- **Own runtime stack.** Compose project `m-academy`, its own containers, PostgreSQL
  instance and volume, Redis instance, object-storage instance and buckets, Celery broker
  and fresh secrets. The legacy stack keeps running untouched; the two share no network,
  volume, database, cache, bucket or credential. Names, ports and buckets are fixed in
  `docs/operations/environments.md`; changing a published port means editing that table in
  the same task.
- Cookie names are namespaced (`m_academy_sessionid`, `academy_csrftoken`). Never use a
  generic cookie name another local project may also set on the same host.

## Change approval
| Change type | Required approver |
|---|---|
| Scope / acceptance criteria (CHARTER) | Project owner |
| Architecture / security boundary / adapter interfaces | Project owner (+ Hub owner for contract changes) |
| New dependency or external service | Technical authority + `pip-audit` clean |
| Production release / phase gate | Project owner |
| Mandatory-requirement exception | Project owner, recorded per Exceptions below |

## Task lifecycle
`[ ]` todo · `[~]` in progress/review (name, date) · `[!]` blocked (reason) · `[x]` done on
main with merge-commit + CI evidence. Phase gates close only after every task in the phase
plus its acceptance criteria are verified.

`LOG.md` entries use these status values (event states, not task states):

- **Status:** Proposed | Approved | Implemented | Tested | Verified | Merged | Released | Rejected | Superseded

Implemented, Tested, Verified, Merged and Released entries require evidence.

## Security and quality rules
- CI gates must pass to merge. Numbering and exact scope are defined in
  `docs/traceability.md` §3: G1 format/lint · G2 types · G3 tests (coverage ≥85% on
  services/selectors) · G4 migrations · G5 OpenAPI (0 warnings) · G6 security scans
  (`pip-audit`, bandit, image scan, `check --deploy`) · G7 import-boundary + tenant
  isolation · G8 E2E + axe smoke · G9 docs check.
- A failed security gate is never bypassed; use the Exceptions mechanism instead.
- CSRF on unsafe browser requests; throttling per route; upload validated by content and size;
  presigned URLs short-lived and key-scoped; CSV export neutralizes formula injection.
- Postgres constraints enforce invariants; indexes begin with `organization_id`; migrations
  committed, reversible, never edited after application.

## Document sync table
A task that changes a fact updates the document that owns it in the same commit. `docs/skills/closing.md` step 3 refers to this table.

| When this changes | Update |
|---|---|
| Scope, acceptance criteria, success measures, risks | `CHARTER.md` (+ LOG entry) |
| An architecture decision (ADR) | `ARCHITECTURE.md` §11, plus `docs/adr/` when a record is needed |
| A decision's value or status | `docs/decisions.md`, then every document that quotes it |
| Task state, current phase, blockers, next action | `STATUS.md` |
| Any completed or approved work | `LOG.md` (append-only) |
| IDs, gate definitions and activation, requirement coverage | `docs/traceability.md` |
| A configuration value, job, message text or report column | `docs/configuration.md`, `docs/background-jobs.md`, `docs/notifications.md`, `docs/reports.md` |
| Ports, containers, buckets, isolation rules | `docs/operations/environments.md` |
| Schema, constraints, progress rules | `docs/domain-model.md` |
| An endpoint, capability or error code | `docs/api.md` |

## Definition of done
A task is `[x]` only when every item holds:
1. Each acceptance criterion in its STATUS row has cited evidence: file+line, test name or command output.
2. The gates that are active for it pass on the merge commit (`docs/traceability.md` §3); none is bypassed or silenced.
3. The documents above are updated, and `python scripts/check_docs.py` (G9) passes.
4. `ruff`, `mypy`, the migrations check and the tests covering the change pass locally.
5. `LOG.md` has one entry with evidence; the STATUS row carries the merge commit and CI link.
6. No orphan TODO: every marker names a task ID from STATUS.

## Commit messages
Conventional Commits, one focused change per commit, English imperative subject of at most 72
characters: `<type>(<scope>): <subject>`, where type is one of `feat`, `fix`, `docs`,
`refactor`, `test`, `build`, `ci`, `chore`, `perf`. The body says why, not what, and names the
task ID (`Refs: T-003`). A commit never contains secrets, `.env`, generated artifacts, `*.log`
or an unrelated file.

## UI and frontend rules
- Strict CSP without `unsafe-inline`: no inline `style=` and no inline `<script>`; styles and
  scripts ship as cacheable files.
- RTL first: use logical properties (`margin-inline-start`, `padding-block`,
  `inset-inline-start`) instead of left/right-specific rules.
- Every user-visible string comes from gettext (`ar` default RTL, `en` secondary); no literal
  copy in templates or scripts.
- Brand: locally hosted Noto Sans Arabic; the wordmark is a text logotype until D-008 is decided.
- Accessibility target is WCAG 2.2 AA: labelled controls, visible focus, keyboard-reachable
  player controls, and no colour-only meaning.

## Dependencies
- Every dependency is pinned to an exact version in `pyproject.toml`; no floating ranges.
- A new dependency or external service needs technical-authority approval and a clean
  `pip-audit` in the same change.
- Upgrading or removing a pinned version is a normal change whose reason goes in the commit body.
- Provider SDKs never appear inside `academy/`: adapters own them.

## AI agent permissions
- Allowed: implement approved tasks end-to-end; run local focused verification; update
  documents per the sync duty; push to task branches; append LOG entries.
- Prohibited: bypassing or disabling a CI gate; touching scope/acceptance criteria; changing
  the Hub contract without owner + Hub-owner approval; merging to main (owner merges PRs);
  storing personal data or secrets; rewriting LOG history.
- Prohibited (environment safety): any Docker command that can reach another project —
  `docker system prune`, `docker volume prune`, `docker network prune`, `docker rm -f`,
  `docker compose down` outside this project, or stopping, restarting, recreating or
  inspecting-modifying the legacy stack (`masheed-academy-*`) and any other project's
  containers. Only this project's own containers may be stopped, and only by the recorded
  project name or PID.
- Prohibited: pushing to a remote or changing repository visibility without owner
  authorization (visibility and documentation publication are D-023).
- A bare «كمل» / «continue» = take STATUS.md → Next action, complete at most one checkpoint,
  commit, push, report, and stop.

## Stop conditions
Stop and ask the project owner (record in STATUS.md open decisions) when: a requirement is
ambiguous or contradictory; a choice affects the data model, security, or adapter interfaces;
Hub-contract facts are needed; CI fails for reasons outside the task; scope would change.

## Exceptions
An exception record must state: justification, risk, compensating controls, a verifiable
removal condition and who verifies it, approver, and review/expiry date. Model:
`docs/exceptions/EXCEPTION-<id>.yaml` (template in the UPDS package).
- A change to an enforcement mechanism (CI gate, check, policy) is its own task; if it cannot
  pass the gate it modifies, an approved exception record must exist before integration and
  be logged.
- Exceptions never renew automatically; renewal requires a new approval record.
- Where feasible, enforce expiry mechanically (for example in the pipeline).
