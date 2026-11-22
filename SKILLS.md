# SKILLS — Index of Repeatable Procedures

> This is an index, not a second rules document. Project authority remains in `RULES.md`.

| Skill | When to use | Path | Last verified |
|---|---|---|---|
| Add/change a model | Any schema change | `docs/skills/model-change.md` | 2026-11-22 |
| Add a service | Any new write behavior | `docs/skills/service.md` | 2026-11-22 |
| Add an API endpoint | New REST operation | `docs/skills/api-endpoint.md` | 2026-11-22 |
| Tenant isolation testing | Every service/selector/endpoint | `docs/skills/tenant-isolation.md` | 2026-11-22 |
| Add an audited action | Any state-changing admin op | `docs/skills/audited-action.md` | 2026-11-22 |
| Close a task / phase gate | End of every task | `docs/skills/closing.md` | 2026-11-22 |
| Record or close a decision | Any `D-NNN` state change | `docs/decisions.md` | 2026-11-22 |
| Architecture decision | Consequential design decision | `docs/adr/README.md` (template + index) | 2026-11-22 |
| Compliance assessment | Periodic conformance check | RULES gates G1–G9 + `docs/traceability.md` §3–§4 | 2026-11-22 |
| Safe AI handoff | Starting/continuing agent work | RULES → AI agent permissions + `STATUS.md` → Next action | 2026-11-22 |

## Adding a skill
Add an entry only when a procedure is recurring or sufficiently complex to justify a
reusable playbook. Detailed skills live in `docs/skills/` with: Purpose, When to Use,
Steps, Validation.

External skills never override project rules, approved decisions, security requirements
or delegated authority.

The UPDS 1.0.0-rc2 package is external to this repository and is not vendored. Where a skill
previously pointed into it, the in-repo equivalent in the table above is authoritative:
decisions in `docs/decisions.md`, ADRs in `docs/adr/`, gates and requirement coverage in
`docs/traceability.md`.
