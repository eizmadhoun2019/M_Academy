# Skill: Add an audited action

**Purpose:** Complete, immutable audit coverage for admin operations.
**When to Use:** Any state-changing admin operation or denied admin check.

## Steps
1. Add the action name to the audited-actions list in ARCHITECTURE §7.
2. Call `audit.record(...)` inside the service transaction (actor, action, object, ids-only metadata).
3. For denied admin operations, record after rolling back the denied write to its savepoint.

## Validation
Test asserts exactly one event with correct actor/object on success, and none when the
operation fails; verify the action appears in the audit API/page filters.
