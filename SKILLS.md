# SKILLS — Index of Repeatable Procedures

> This is an index, not a second rules document. Project authority remains in `RULES.md`.

| Skill | When to use | Path | Last verified |
|---|---|---|---|
| Add/change a model | Any schema or constraint change | `docs/skills/model-change.md` | 2026-11-25 |
| Implement or review a UI screen | Any screen, shell, dialog, state or responsive change | `docs/skills/ui-screen.md` | 2026-11-25 |
| Add a service | Any new write behavior | `docs/skills/service.md` | 2026-11-25 |
| Add an API endpoint | New REST operation | `docs/skills/api-endpoint.md` | 2026-11-25 |
| Tenant isolation testing | Every service/selector/endpoint/task/export | `docs/skills/tenant-isolation.md` | 2026-11-25 |
| Add an audited action | Any state-changing admin/security op | `docs/skills/audited-action.md` | 2026-11-25 |
| Add/change a permission or role | Any RBAC catalogue or default-role change | `docs/skills/permission-change.md` | 2026-11-25 |
| Close a task / phase gate | End of every task/checkpoint | `docs/skills/closing.md` | 2026-11-25 |
| Record or close a decision | Any `D-NNN` state change | `docs/decisions.md` | 2026-11-25 |
| Architecture decision | Consequential design decision | `docs/adr/README.md` (template + index) | 2026-11-25 |
| Compliance assessment | Periodic conformance check | RULES gates G1–G12 + `docs/traceability.md` §3–§4 | 2026-11-25 |
| Safe AI handoff | Starting/continuing agent work | RULES → «كمل» protocol + `STATUS.md` → Next action | 2026-11-25 |

## Adding a skill
Add an entry only when a procedure is recurring or sufficiently complex to justify a reusable
playbook. Detailed skills live in `docs/skills/` with: Purpose, When to Use, Steps, Validation.

External skills never override project rules, approved decisions, security requirements or
delegated authority.

The UPDS 1.0.0-rc2 package is external to this repository and is not vendored. Where a skill
previously pointed into it, the in-repo equivalent above is authoritative: decisions in
`docs/decisions.md`, ADRs in `docs/adr/`, gates and requirement coverage in
`docs/traceability.md`.

## Handoff checklist (new agent or developer)
1. Read `README.md` → `RULES.md` → `CHARTER.md` → `ARCHITECTURE.md`.
2. Read `STATUS.md`, `docs/plan.md`, then the owning document for the next task.
3. Run `git status`, `git log -5 --oneline`, and `python scripts/check_docs.py`.
4. Confirm the branch/task eligibility and dependencies; do not start a later task out of order.
5. Follow the «كمل» protocol; stop only for the listed approval conditions.
