# TRACEABILITY — IDs, Sources of Truth and Gates

**Status:** Canonical reference. Kept current by every task that closes (see
`docs/skills/closing.md`).
**Last updated:** 2026-11-22

## 1. Identifier scheme (current)

| Prefix | Meaning | Canonical location |
|---|---|---|
| `REQ-NN` | Charter requirement with acceptance criteria | `CHARTER.md` §5 |
| `T-NNN` | Build task | `STATUS.md` → Active work |
| `GATE-N` | Phase gate | `STATUS.md` |
| `D-NNN` | Deferred decision | `docs/decisions.md` |
| `ADR-NNN` | Architecture decision record | `ARCHITECTURE.md` §11, files under `docs/adr/` |
| `EXCEPTION-<id>` | Approved deviation from an enforcement mechanism | `docs/exceptions/` |
| `G1`–`G9` | CI quality gates | §3 below and `RULES.md` |

**Rule:** tasks use `T-NNN`. The legacy `P0-NN` / `P1-NN` plan numbers are retired and must
not appear in new text. Use §2 to translate any surviving occurrence.

## 2. Legacy plan IDs → current tasks

| Legacy | Current | Scope |
|---|---|---|
| P0-13 | T-013 | UI foundation: tokens, shell, RTL/LTR |
| P0-15 | T-015 | Hub HTTP integration: signed identity, webhooks, Hub adapters |
| P1-05 | T-019 | Assignments, auto-enroll on `member_changed`, gating |
| P1-12 | T-023 | Learner and management web pages |
| P1-19 | T-024 | Load test at design capacity |
| P1-22 | T-024 | Pilot and manager survey |
| P1-24 | T-016 | Academy-managed permission grants |

## 3. CI quality gates

Referenced as “gate G7” and similar in skills and RULES. Definitions here are normative.

**Activation.** A gate is fully applicable only from the task that first creates what it
measures. Until then it runs and reports its state explicitly — an inactive gate exits 0 with
a printed reason, so “green” never hides “not run”. The list below is the single place that
records which gates are live, and it is updated in the task that activates a gate.

| Gate | Check | Active | Fails the merge when |
|---|---|---|---|
| G1 | `ruff format --check` + `ruff check` | T-001 | Any finding |
| G2 | `mypy` (public functions typed) | T-001 | Any error |
| G3 | `pytest` with coverage | T-001 (suite), coverage threshold from T-003 | Any failure, or services/selectors coverage < 85% |
| G4 | `makemigrations --check --dry-run` + migrate forward/back | T-001 | Missing or non-reversible migration |
| G5 | OpenAPI schema build | T-001 | Any warning |
| G6 | Security scans: `bandit`, `pip-audit`, image scan, `check --deploy` | T-001 (all four sub-checks) | Any unresolved high/critical finding without an approved exception |
| G7 | Import boundary + tenant isolation suites | import boundary: T-001, enforcing from T-003 (`academy/` exists; `scripts/gate_imports.py` plus `tests/test_import_boundary.py` prove the gate can fail); tenant half: T-010 | `academy` imports host/`host_stub`, or any cross-org leak |
| G8 | E2E + axe smoke | T-023 (`tests/e2e/` non-empty; a guard job decides) | Journey failure, or axe critical/serious violation |
| G9 | Documentation check (links, IDs, required sections) | T-001 | Broken reference or missing required document section |

## 4. Requirement → task → evidence

| REQ | Task(s) | Evidence location |
|---|---|---|
| REQ-01 | T-001 | CI run on the merge commit; `/healthz` 200 |
| REQ-02 | T-004 | Adapter contract suites (4) |
| REQ-03 | T-006, T-007, T-008 | Migration apply/reverse; isolation suite |
| REQ-04 | T-005, T-012 | On-commit tests; trigger blocks UPDATE/DELETE |
| REQ-05 | T-013 | Renders at 3 viewports in ar/en; axe |
| REQ-06 | T-017 | Publish validation + immutability tests |
| REQ-07 | T-018 | End-to-end media pipeline test |
| REQ-08 | T-019 | Assignment matrix + auto-enroll test |
| REQ-09 | T-020 | Progress matrix (see `docs/domain-model.md` §7) |
| REQ-10, REQ-11 | T-021 | Idempotency tests with frozen time |
| REQ-12 | T-022 | Query-count and scope tests; CSV formula safe |
| REQ-13 | T-016 | Capability matrix in DRF and web, both modes |
| REQ-14 | T-023 | Manual check record in LOG |
| REQ-15–REQ-20 | T-024 | Journey, E2E, load, ops, security, privacy, pilot evidence |

## 5. Sources of truth (never restate elsewhere)

| Fact | Only canonical file |
|---|---|
| Deferred decisions and their values | `docs/decisions.md` |
| Entities, fields, constraints, state machines, progress algorithm | `docs/domain-model.md` |
| API surface, error codes, capabilities per route | `docs/api.md` |
| NFR targets and capacity assumptions | `docs/performance-profile.yaml` (owned by CHARTER) |
| Task state, next action, blockers | `STATUS.md` |
| History | `LOG.md` |
| Hub ↔ Academy wire contract | `docs/hub-contract.md` |
| Repository identity, stack names, host ports, buckets, cookies, isolation rules | `docs/operations/environments.md` |
| Settings, upload policy, HLS parameters, pagination, throttles | `docs/configuration.md` |
| Celery task names, schedules, retries, idempotency | `docs/background-jobs.md` |
| Report metrics, columns, CSV format | `docs/reports.md` |
| Notification and reminder copy (ar/en), channels, dedupe keys | `docs/notifications.md` |

## 6. Verification
`docs/traceability.md`, `STATUS.md` and `LOG.md` must agree: every `T-NNN` in STATUS exists
here, every `REQ` maps to at least one task, and no retired `P0-/P1-` identifier remains:

```bash
grep -rn "P0-[0-9]\|P1-[0-9]" --include=*.md . | grep -v "docs/traceability.md" | grep -v "docs/decisions.md" || echo "clean"
```
