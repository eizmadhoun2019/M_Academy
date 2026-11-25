# Skill: Add an audited action

**Purpose:** Complete, immutable audit coverage for administrative and security operations.
**When to Use:** Any state-changing admin/security operation, and every denied admin attempt.

## Steps
1. Add the action name to `docs/access-control.md` §7 (the audited-action list) and use the
   `domain.verb` form (`membership.invited`, `membership.roles_changed`, `auth.login_failed`).
2. Call `audit.record(...)` inside the service transaction with: action, actor user UUID,
   actor membership (null for platform/system), company (null for platform events), target type,
   target UUID, ids-only metadata and a reason where the operation requires one.
3. For a denied admin operation, roll back to the savepoint and record the denial; never store
   the attempted payload, password, token or email.
4. Platform read-only access to a company writes one `platform.access_started` event with the
   company id and the operator; it is visible in S2, not in the company's S1 feed.
5. Never expose delete/edit on audit rows; a correction is a new event.

## Validation
Test asserts exactly one event with the correct actor/company/target on success, one denial event
on refusal, and no event or partial write on an unrelated failure. Verify the action appears in
the audit filters and that no secret/PII field is present in metadata.
