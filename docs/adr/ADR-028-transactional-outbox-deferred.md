# ADR-028 — Transactional outbox assessed and deferred

- **Status:** Accepted (2026-11-25) — deferral
- **Date:** 2026-11-25
- **Deciders:** Project owner
- **References:** D-041; REQ-10, REQ-11, REQ-26

## Context
Notifications are written to `NotificationLog` in the same transaction as the business change,
then a task sends them. Delivery to SMTP is at-least-once with a unique dedupe key; after-commit
handlers are used for domain events. Hub mirroring, when enabled, has its own retry/circuit and
event-id idempotency. There is no current requirement for exactly-once delivery to an external
system across a process crash.

## Decision
**Do not adopt a general transactional outbox in H1.5.** Keep the local state as the source of
truth: the `NotificationLog` row (or `ReminderLog`) is written before sending, the unique key is
the idempotency gate, and a sweeper retries. Add a real outbox only when an external consumer
needs guaranteed publication that cannot be reconstructed from local state (for example a future
event bus or billing integration), with a design for relay ordering, retention and poison
messages.

## Rationale
- The notification table already provides the durable “intent” record and dedupe key.
- SMTP and Hub adapters tolerate duplicates/retries by design; exactly-once is not promised.
- An outbox adds a relay, another table, monitoring and failure modes before the need exists.

## Alternatives considered
- **Generic outbox now:** rejected as overengineering.
- **Publish directly from the request after commit:** rejected; a crash loses the send intent.
- **No durable intent:** rejected; notifications would be silently lost.

## Consequences
- Positive: simpler pipeline, fewer moving parts, local state is inspectable.
- Negative: an external system may receive duplicates; consumers must be idempotent.
- Revisit when a non-idempotent external consumer or an audit/billing guarantee appears.

## Risks and mitigations
Lost notification after commit → sweeper + durable row. Duplicate delivery → dedupe key +
consumer idempotency. Future outbox migration → keep event ids stable and actions idempotent.

## Dependencies
`docs/background-jobs.md` §1, `docs/notifications.md` §1, `docs/domain-model.md` §2.11–§2.12.
