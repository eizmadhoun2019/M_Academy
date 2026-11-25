# SECURITY — Controls, Privacy and Data Protection

**Status:** Canonical. Charter: REQ-18, REQ-19, REQ-22, REQ-23, REQ-26. Authorization rules:
`docs/access-control.md`. Deployment controls: `docs/operations/environments.md`.
**Last reviewed:** 2026-11-25
**Baseline:** OWASP ASVS Level 1 + OWASP Top 10 (2021). Deviations need an approved exception.

## 1. Assets and trust boundaries
Assets: account credentials and sessions; MFA secrets and recovery codes; company training
content and media; enrollment/progress/completion records; membership and department data;
audit trail; configuration secrets (DB, storage, SMTP, Hub keys); backups.
Boundaries: browser ↔ application; application ↔ PostgreSQL/Redis; application ↔ object
storage (presigned, company-prefixed keys); application ↔ SMTP; application ↔ optional Hub;
company ↔ company; platform administrator ↔ company data.

Threats considered: credential stuffing and password spraying; account enumeration; session
theft/fixation; privilege escalation and confused-deputy through client-supplied company ids;
cross-company access through an unscoped query, cache, export, task or storage key; IDOR on
media; stored XSS through course text; CSV formula injection; malicious uploads; SSRF through
URL fields (none accepted); secret leakage in logs/repository; supply-chain compromise;
destructive operator error on a shared host.

## 2. Authentication
- Django `authenticate()` with a Custom User (`USERNAME_FIELD=email`); Argon2 hasher first
  (verified available in the deployment image), PBKDF2 as fallback for existing hashes.
- Password policy: minimum 12 characters, Django's common-password and numeric/similarity
  validators, no forced composition or rotation; breached-password lists may be added later.
- Email verification is required before tenant access; unverified accounts can resend (throttled).
- Password reset uses a single-use, hashed, 60-minute token; the response is identical whether or
  not the email exists; a successful reset revokes all other sessions.
- Invitations: single-use hashed token, 7-day expiry, bound to email + company + roles; accepting
  sets the password and verifies the email; re-inviting invalidates the previous token. An email
  that already has a membership in any company is rejected (`already_member`); a platform account
  needs no invitation or membership.
- Login errors are generic (`INVALID_CREDENTIALS`); timing does not reveal account existence.
- Throttling: 5 failures per email+IP per 15 min and 20 per IP per 15 min, exponential backoff
  and a temporary lock; counters in Redis; each failure and lock is audited with a truncated IP.
- **TOTP MFA** (RFC 6238, 30 s, ±1 step) is mandatory for Super Admin and Company Admin and
  available to every account. Enrolment requires password re-entry; the secret is encrypted at
  rest with a key from `ACADEMY_MFA_ENCRYPTION_KEY`; 10 single-use recovery codes stored hashed.
  Disabling MFA requires password + a current TOTP/recovery code and is audited. WebAuthn is
  future work and must not be half-implemented.
- Development login exists only when `DEBUG=True` **and** `ACADEMY_DEVELOPMENT_LOGIN=True` **and** the
  settings module is a development/test module. It is absent from production URLs and a test
  asserts that it cannot be enabled in production settings.
- No authentication secret is written to logs, audit payloads, error reports or API responses.

## 3. Sessions and request protection
- Django sessions in the configured backend (database in production); cookie
  `m_academy_sessionid`, `HttpOnly`, `Secure` in production, `SameSite=Lax`, `Path=/`.
- Absolute lifetime 12 h, idle timeout 30 min enforced by server-side last-activity checks
  (coarse writes, not every request); session key rotates on login and privilege change;
  password change/reset and suspension revoke all sessions; users can list and revoke sessions.
- CSRF: Django middleware, cookie `academy_csrftoken`, token on every state-changing form and
  `X-CSRFToken` on fetch; `CSRF_TRUSTED_ORIGINS` from configuration only.
- Security headers: HSTS (1 year; `includeSubDomains` and preload only after the owner confirms
  all subdomains), `X-Content-Type-Options: nosniff`, `Referrer-Policy:
  strict-origin-when-cross-origin`, `Permissions-Policy` denying camera/microphone/geolocation,
  `Cross-Origin-Opener-Policy: same-origin`, `X-Frame-Options: DENY` / `frame-ancestors 'none'`.
- CSP (no `unsafe-inline`, no `unsafe-eval`): `default-src 'self'; script-src 'self'; style-src
  'self'; img-src 'self' data: blob:; media-src 'self' blob: https://<storage-host>;
  connect-src 'self' https://<storage-host>; worker-src 'self' blob:; font-src 'self';
  frame-ancestors 'none'; base-uri 'self'; form-action 'self'; object-src 'none'`.
  The storage host is configuration; templates emit no inline style/script.

## 4. Authorization and tenant isolation
Canonical: `docs/access-control.md`. Non-negotiables: deny by default; company context derived from the caller's single membership
(or an explicit authorized platform company id); `UNIQUE (user_id)` prevents a second membership;
route permission + service recheck + object scope + query filter + DB constraint;
platform access is read-only and audited; no authority accepted from request bodies and no
company-selection/switching path exists; hidden UI is not a control; permission changes and
denials are audited (denials sampled).

## 5. Input, output and uploads
- All input validated by DRF serializers/forms; enums and ids validated against the active
  company; unknown fields rejected.
- ORM only; no string-built SQL. Raw SQL requires parameter binding and review.
- Autoescaping stays on; user HTML is never marked safe; course text is plain text or a
  sanitized allowlist (no scripts, no event attributes, no `javascript:` URLs).
- Redirects only to same-origin or allowlisted paths; no user-controlled absolute URLs.
- CSV export: values beginning with `= + - @`, TAB or CR are prefixed with `'`; exports are
  scoped, streamed, audited and rate-limited.
- Uploads: size limits (`docs/configuration.md`), extension + MIME sniff agreement, images
  jpeg/png/webp only (SVG rejected), video mp4/mov only, object keys generated server-side,
  company prefix mandatory, media served via short-lived presigned URLs, never from a public
  bucket. ffmpeg runs with a fixed argument list and no user-supplied flags. Malware scanning is
  deferred (documented gap, revisit before external uploads at scale).
- Errors: stable machine code + generic message; stack traces and provider errors never reach
  the client; 404 is used instead of 403 when revealing existence would cross tenants.

## 6. Personal data (minimal, registered)
| Data | Purpose | Where | Retention | Access |
|---|---|---|---|---|
| Email | Login, verification, reset, invitations, notifications | `User.email`, `Invitation.email` | Account life + 30 d; invitations 7 d after expiry | Self, Company Admin (own company), platform user admin |
| Display name | UI, reports, audit readability | `User.display_name` | Same as account | Same |
| Preferred language | Localized mail/UI | `User.preferred_language` | Same as account | Self, admins |
| Membership metadata (department, state, dates) | Access and reporting | `Membership` | Life of membership + 5 y history (training evidence) | Scoped managers/admins |
| Security metadata (last login, MFA state, session times) | Account security | `User`, `UserSession`, `MFADevice` | Sessions 30 d; MFA until removed; last login account life | Self, platform security admin |
| Login attempt (truncated IP, outcome, time) | Abuse detection | Redis + auth audit | 90 d | Security/platform audit |
| Audit actor UUID | Accountability | `AuditEvent` | 5 y | Company Auditor/Admin, platform audit |
| Training progress/completion | Product purpose | learning tables | 5 y (completion), 12 mo raw ranges | Learner, scoped managers |

Not collected: national ID, phone, address, birth date, photo, salary, health, free-form HR
notes, precise location, advertising identifiers. **Names and emails are now stored** because
local authentication and notifications require them; this supersedes ADR-002 and is bounded by
this table (D-037).

Rules: collect at the point of need; no silent enrichment; no email in application logs, metric
labels or trace tags (use user UUID); exports/anonymization per D-037; data-subject requests are
handled by the platform owner with an audited admin command.

## 7. Retention and deletion
| Data | Retention | Mechanism |
|---|---|---|
| Account PII | While any active membership; 90 d after last membership removal, then anonymized (email replaced with a non-routable value, name replaced) | `accounts.anonymize_expired` job, audited |
| Sessions | 30 d after last use / on revocation | `accounts.purge_sessions` |
| Verification/reset/invitation tokens | 24 h / 60 min / 7 d; purged after use + 30 d | `accounts.purge_tokens` |
| Notification/reminder logs | 90 d | `notifications.purge_logs` |
| Stale uploads | 24 h | existing cleanup job |
| Audit | 5 y (platform may extend) | no deletion by application code |
| Backups | 30 daily, 12 monthly; encrypted | lifecycle policy |

Deletion is soft for history-bearing rows (company archive, membership removed, account
anonymized); hard deletion requires a platform-admin command with confirmation, audit and a
backup check. Legal holds override retention and are recorded.

## 8. Secrets and configuration
- Secrets only from environment/secret manager; never committed, never in `.env.example` values,
  never printed. `.env` stays untracked. Separate credentials per environment; least-privilege DB
  and storage users; Hub keys and SMTP credentials rotatable without a code change.
- `DEBUG=False`, `SECRET_KEY` non-default and ≥50 chars in production; startup check refuses
  insecure production settings (including dev login, wildcard hosts and missing HSTS).
- Secret rotation: sessions and tokens invalidated where relevant; rotation procedure in
  `docs/operations/environments.md` §7.
- CI uses placeholder values only; no repository secret is required for tests.

## 9. Audit and logging
- Append-only `AuditEvent` (DB trigger blocks UPDATE/DELETE); fields per
  `docs/access-control.md` §9; no secrets, tokens, passwords, full request bodies or unnecessary
  PII.
- Application logs are structured JSON with request id, route, status, duration, company id and
  actor UUID; email/name excluded; log level configurable; retention 30 days on the log sink.
- Security events (failed logins, lockouts, MFA changes, permission changes, platform access,
  backup failures) are alertable (D-039).
- Error reporting scrubs cookies, authorization headers and form bodies.

## 10. Dependencies, supply chain and infrastructure
- Pinned dependencies; `pip-audit` and image scanning in CI (G6); no unpinned transitive tool
  installs in Dockerfiles; base images pinned by digest where practical.
- Minimal image (no pip/setuptools at runtime, non-root user, read-only root where feasible);
  ffmpeg from the distro with a fixed version.
- TLS terminated at the reverse proxy; internal services on a private network; PostgreSQL/Redis
  not publicly exposed; storage bucket private.
- Backups encrypted at rest and in transit, access restricted, restore tested (T-034).
- Operator commands are project-scoped (`-p m-academy`); destructive Docker commands are
  prohibited (`RULES.md`).

## 11. Incident response
1. Detect (alert/monitor/report) → 2. Triage severity and affected companies → 3. Contain
(disable account/integration, rotate secrets, block source) → 4. Preserve evidence (audit,
logs, snapshots; no tampering) → 5. Eradicate and recover (restore if needed) → 6. Notify the
owner and, where legally required, affected parties/regulator within the applicable window →
7. Post-incident review with actions and an entry in `LOG.md`.
Contact and severity levels are maintained in `docs/operations/environments.md` §10. Never
delete evidence to “clean up”.

## 12. Verification and known gaps
Before GATE-1 (T-034): ASVS L1 checklist with evidence, dependency/image scan clean, CSP and
headers verified on staging, auth/MFA/session/privilege tests green, isolation matrix green,
backup restore proven, privacy export/anonymization test, and a documented penetration-test
scope (external test optional before H2). Evidence is recorded in `STATUS.md`.
Known deferred gaps: no malware scanning of uploads; no WebAuthn; no RLS; no WAF/CDN controls;
no external penetration test; no formal SOC 2/ISO certification. Each is a risk accepted for
H1.5 and revisited at H2 — not a claim of compliance.
