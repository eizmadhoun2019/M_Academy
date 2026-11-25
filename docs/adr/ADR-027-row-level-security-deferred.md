# ADR-027 — PostgreSQL row-level security assessed and deferred

- **Status:** Accepted (2026-11-25) — deferral
- **Date:** 2026-11-25
- **Deciders:** Project owner
- **References:** D-040; REQ-03, REQ-21

## Context
PostgreSQL RLS could add a database-level isolation layer on top of ORM scoping. A mis-scoped
query would return no rows instead of leaking. The application currently uses one database role,
Django ORM scoping, composite FKs and an isolation suite; background workers, migrations and
platform (cross-company, audited) access all run through the same connection.

## Decision
**Defer RLS in H1.5.** Keep `TenantModel` + `organization_id` + composite FKs + service scoping +
the G7 isolation suite as the enforcement stack. Revisit RLS when there is a concrete requirement
for defense-in-depth against application bugs or a compliance mandate, and only with a design for:
- a non-owner application role and a separate migration role;
- session GUC `app.organization_id` set per transaction/request, cleared on release;
- worker/task context and platform-access bypass policy;
- policies on every tenant table (including audit and media), with `WITH CHECK`;
- performance measurement on the largest tables;
- a migration/rollback and test plan proving both allow and deny paths.

## Rationale
- RLS is high-value only after the data model and access paths stabilize; adding it during the
  tenancy migration multiplies failure modes.
- Connection pooling and Celery make session GUC handling non-trivial; a wrong default can hide
  rows or break background jobs.
- Current enforcement already includes DB-level tenant integrity; the marginal risk reduction
  does not justify the H1.5 cost.

## Alternatives considered
- **Adopt RLS now:** rejected for migration risk and operational complexity.
- **Separate schema/database per company:** rejected (ADR-026).
- **No DB-level defense:** rejected; composite FKs remain mandatory.

## Consequences
- Positive: simpler H1.5 migration and operations; no pooling/GUC pitfalls.
- Negative: an application query bug remains the primary leak risk; mitigated by tests and review.
- Revisit trigger: compliance requirement, a confirmed near-miss, or >10 companies with
  third-party access.

## Risks and mitigations
False sense of security → document that ORM scoping is the enforcement, not optional. Future RLS
retrofit → keep company columns non-null and indexed so policies are feasible.

## Dependencies
`docs/domain-model.md` §3, `docs/security.md` §2, `docs/access-control.md` §7.
