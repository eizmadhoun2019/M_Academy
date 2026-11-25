# ADR-024 — Public website on `/`, application under `/academy/`, Academy-owned origin

- **Status:** Accepted (2026-11-25)
- **Date:** 2026-11-25
- **Deciders:** Project owner
- **Supersedes:** ADR-010 (Hub reverse proxy as the public origin), ADR-014 (Hub entry)
- **References:** D-035, D-043; REQ-24, REQ-26

## Context
The Hub proxy previously owned the public origin and Academy lived behind `/academy` with no
public site of its own. That made the academy invisible without Hub, prevented a normal public
home/SEO presence, and tied TLS, cookies and CSRF to another deployment.

## Decision
Academy serves its own origin: a public website at `/` (home, about, programmes, contact,
privacy/terms) and the authenticated application under `/academy/`. Login, reset, verification,
invitation acceptance are Academy pages; after login the server derives the single company and
redirects to the permitted dashboard. There is no company-selection page. The Hub reverse-proxy topology
remains documented but is optional and dormant; enabling it requires both owners and the D-035
review.

## Rationale
- A standalone product needs its own entry point and brand surface.
- Separate public and application shells simplify caching, CSP and cookie scope.
- A fixed `/academy/` prefix keeps a future proxy possible without changing application routes.

## Alternatives considered
- **Hub origin only:** rejected; blocks standalone launch and pilot.
- **Application at `/` with public pages on a separate host:** rejected; splits branding and
  complicates links/cookies.
- **Subdomain per company:** deferred to white-label (H2); not needed for H1.5.

## Consequences
- Positive: independent TLS/DNS, public site, simple session cookies (`Path=/academy/`), clear
  cache boundaries and one unambiguous post-login destination.
- Negative: Academy owns certificate renewal, HSTS, CDN and DNS operations.
- The Hub proxy, if ever enabled, must preserve the prefix; `FORCE_SCRIPT_NAME` remains supported.
- Revisit: custom domains and white-label in H2.

## Risks and mitigations
DNS/TLS expiry → monitored certificate and an alert (T-034). Public/private leakage → public
templates receive no application context; tests assert no session data on `/`. Proxy re-enable
drift → T-033 checklist and contract tests.

## Dependencies
`docs/operations/environments.md` §1/§11, `docs/configuration.md` §4, `docs/hub-contract.md` §6.
