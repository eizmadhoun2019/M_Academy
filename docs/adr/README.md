# ADR index

Architecture decision records for Masheed_Academy. The summary list lives in
`ARCHITECTURE.md` §12, which is normative; this directory holds the expanded record for decisions
that needed one.

**Naming:** `ADR-NNN-<slug>.md`. Never renumber an accepted ADR; supersede it with a new one and
mark the old one `Superseded by ADR-MMM`. **ADR numbers 15–22 are reserved legacy numbers and must
not be reused**; new records start at ADR-023.

**Template:**

```markdown
# ADR-NNN — Title

- **Status:** Proposed | Accepted | Superseded by ADR-MMM
- **Date:** YYYY-MM-DD
- **Deciders:** Project owner / technical authority
- **References:** D-NNN, REQ-NN

## Context
What forces are in play.

## Decision
What we will do.

## Rationale
Why this option.

## Alternatives considered
What was rejected and why.

## Consequences
What becomes easier, what becomes harder, what must be revisited.

## Risks and mitigations
Known risks and their controls.

## Dependencies
Owning documents.
```

| ADR | Title | Status |
|---|---|---|
| ADR-001 | Django + PostgreSQL + Redis + Celery modular monolith | Accepted (2026-11-22) |
| ADR-002 | Opaque `user_ref`, no local user FK, no stored names/emails | Superseded by ADR-023 |
| ADR-003 | `organization_id` on every tenant table; `for_org` scoping | Accepted (extended by ADR-026) |
| ADR-004 | Adapter seams (identity, organization, notify, storage) + `host_stub` | Accepted |
| ADR-005 | Domain events emitted on commit | Accepted |
| ADR-006 | UUID primary keys | Accepted (UUIDv7 deferred, D-039) |
| ADR-007 | Append-only audit ledger | Accepted |
| ADR-008 | Presigned direct upload + ffmpeg HLS | Accepted |
| ADR-009 | Server-authoritative progress with merged watched ranges | Accepted |
| ADR-010 | Hub reverse proxy as the public origin | Superseded by ADR-024 |
| ADR-011 | Academy grants combined with Hub role defaults | Superseded by ADR-025 |
| ADR-012 | Membership read from Hub on demand; no local membership | Superseded by ADR-026 |
| ADR-013 | Watched coverage as merged ranges on one progress row | Accepted |
| ADR-014 | Dual-mode H1 access, `grants_only`, local suspension | Superseded by ADR-023/024/025 |
| ADR numbers 15–22 | Reserved legacy numbers — never reuse | Retired |
| [ADR-023](ADR-023-standalone-local-identity.md) | Standalone-first platform with local accounts and minimal stored PII | Accepted (2026-11-25) |
| [ADR-024](ADR-024-public-origin-and-path-layout.md) | Public site on `/`, application under `/academy/`, Academy-owned origin | Accepted (2026-11-25; direct post-login routing, D-043) |
| [ADR-025](ADR-025-dynamic-scoped-rbac.md) | Dynamic scoped RBAC replacing Hub roles and coarse capabilities | Accepted (2026-11-25; single-membership context, D-043) |
| [ADR-026](ADR-026-organizations-memberships-departments.md) | First-class organizations, memberships, departments with composite FKs | Accepted (2026-11-25); amended by D-043 |
| [ADR-027](ADR-027-row-level-security-deferred.md) | PostgreSQL RLS assessed and deferred | Accepted (2026-11-25) |
| [ADR-028](ADR-028-transactional-outbox-deferred.md) | Transactional outbox assessed and deferred | Accepted (2026-11-25) |

ADRs 001–014 are summarized in `ARCHITECTURE.md` §12; expanded files exist where the decision
needed one. A superseded ADR is historical context, not an active instruction.
