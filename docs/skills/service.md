# Skill: Add a service (business operation)

**Purpose:** Keep all write logic in the service layer, atomic and event-driven.
**When to Use:** Any new write behavior.

## Steps
1. Signature: `def verb_noun(*, organization_id, actor_ref, ...)` in `academy/services/<area>.py`.
2. Validate capability and scope (effective-capability service) and business rules; raise
   `academy.exceptions.*`.
3. `with transaction.atomic():` perform writes via `.for_org(organization_id)`.
4. Emit events with `emit_on_commit(...)`; never call notifications/handlers directly.
5. Record an `AuditEvent` in the same transaction when it is a state-changing admin op.

## Validation
Tests: success, each rule violation, permission denied, wrong organization, idempotency
if retryable; module coverage ≥ 85%; no logic leaked into views/tasks/serializers.
