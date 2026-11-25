# ADR-023 — Standalone-first platform with local accounts and minimal stored PII

- **Status:** Accepted (2026-11-25)
- **Date:** 2026-11-25
- **Deciders:** Project owner
- **Supersedes:** ADR-002 (opaque user refs, no local accounts), ADR-014 (dual-mode access)
- **References:** D-032, D-033, D-037; REQ-19, REQ-21, REQ-22, REQ-26

## Context
The original design treated Masheed Hub as the identity provider and the only public entry point,
stored no names or emails, and used opaque `user_ref` strings. That made the academy unusable
without Hub, coupled account lifecycle and mail to an external team, and blocked local
authentication, invitations and MFA. The product is now an independent multi-company academy;
Hub must be optional.

## Decision
Academy is **standalone-first**: Django Custom User with UUID primary key and email login, local
sessions, verification, reset, invitations, TOTP MFA and local SMTP mail. A `User` is a person;
a `Membership` links that person to a company. Minimal PII is stored (email, display name,
optional phone, locale, time zone, auth metadata) because it is required to authenticate and
address messages. Hub may later be enabled as an identity adapter that maps to the same local
entities, but it never owns the only copy of an account.

## Rationale
- The academy must boot, sign in, mail and report without any Hub credential or endpoint.
- Email is required for verification, reset and notifications; refusing to store it makes the
  security model impossible.
- Local accounts allow invitations, MFA, session revocation, audit attribution and company
  administration without a second team.
- A single local model keeps Hub optional rather than architecturally central.

## Alternatives considered
- **Keep Hub-only identity:** rejected; violates independence and blocks pilot onboarding.
- **Store email only, no name:** rejected; reports and admin screens need a display name, and
  resolving it per request would require Hub.
- **External IdP (Auth0/Keycloak):** deferred; adds a service, cost and failure mode without a
  current requirement.

## Consequences
- Positive: independent operation, real account lifecycle, auditable actors, MFA, local mail.
- Negative: Academy now owns PII, retention, export/anonymization and breach obligations.
- Migration: legacy `user_ref` values map to accounts; unresolved identities remain disabled.
- Revisit: SSO/SCIM or external IdP when a customer requires it (H2/H3).

## Risks and mitigations
PII exposure → minimal fields, access control, no PII in logs/audit metadata, retention and
anonymization tests (T-034). Account takeover → Argon2, throttling, MFA for admins, session
revocation. Migration loss → owner-provided email mapping, dry-run, reconciliation, backup.

## Dependencies
`docs/security.md` §4–§6, `docs/domain-model.md` §2.0, `docs/migration-h1.5.md`.
