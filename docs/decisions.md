# DECISIONS — Single Decision Register

**Status:** Canonical. This is the only place where deferred decisions live.
**New decisions continue after `D-030`**. D-018…D-022 are retired legacy numbers and are never reused.
**Last updated:** 2026-11-23
**Owner of this file:** Project owner (decisions cannot be closed by the agent alone).

## How to use
- Every deferred decision has exactly one ID here. `STATUS.md` no longer lists decisions;
  it links to this file.
- **Status values:** `Open` (blocks the named task) · `Defaulted` (build proceeds on the
  documented default; the owner may override at any time before the named gate) ·
  `Confirmed` (owner decided, value recorded) · `Retired` (superseded; see mapping).
- `Defaulted` decisions are recorded so that no task waits on them. Overriding a
  `Defaulted` decision is a normal change; it needs a LOG entry and propagation to the
  affected documents, not a rebuild.
- A decision that would change scope, the data model, the security boundary, or an adapter
  interface must still be confirmed by the owner (see RULES → Change approval).

## Register

### Blocking or defaulted

| ID | Decision | Status | Value / default in force | Owner | Needed by | Impact if still undecided |
|---|---|---|---|---|---|---|
| D-001 | Video storage hosting | Open | Development and test use MinIO in compose. Production provider (self-hosted MinIO vs managed S3-compatible) is not chosen. The Storage adapter makes this configuration, not code. | Project owner | Before T-018 production config | Production media cannot be deployed. Does not block T-018 implementation against MinIO. |
| D-002 | Business time zone | Defaulted | Storage in UTC always. `ACADEMY_BUSINESS_TZ` defaults to UTC; reminders and due-date reminders are sent at 08:00 in the business zone. | Project owner | T-021 | Reminder scheduling uses UTC; due dates displayed in UTC. |
| D-003 | Retention periods and legal basis | Defaulted | ARCHITECTURE §5 defaults: completion and audit 5 y, watched-ranges compaction 12 mo, notification and reminder logs 90 d, stale uploads 24 h. Configurable per table. | Management + legal | GATE-1 | Defaults apply; legal confirmation still required before go-live. |
| D-004 | Signed identity format | Defaulted | HMAC-SHA256 `kid.payload.signature` envelope exactly as `docs/hub-contract.md` §2. (Was `D-018`.) | Project owner + Hub owner | T-015 | Verification is implemented against the documented format; a JWT variant would need a replacement verifier (`ACADEMY_HUB_IDENTITY_VERIFIER`). |
| D-005 | Academy upstream domain and TLS ownership | Open | Private HTTPS upstream assumed; hostname, certificate owner and allowlisted proxy CIDRs not assigned. (Was `D-020`.) | Project owner + operations | Production deploy | Blocks production ingress only. |
| D-006 | NFR target confirmation | Defaulted | `docs/performance-profile.yaml` values as approved with CHARTER 2.1. | Project owner | T-024 load test | Targets are used as-is; a deviation must be recorded with owner acceptance. |
| D-007 | Supported browsers and devices | Defaulted | Latest two versions of Chrome, Edge, Firefox, Safari and Samsung Internet; 360/768/1280 px viewports; Android mid-range as the performance reference device. | Project owner | T-024 E2E | E2E runs the default matrix. |
| D-008 | Brand font and wordmark asset | Defaulted | Noto Sans Arabic hosted locally; no wordmark asset in Phase 1 (text logotype). | Management | Final branding | UI ships with the fallback font. |
| D-009 | KPI values (`[X]` in CHARTER §9) | Open | Placeholders remain in CHARTER §9. | Project owner | Pilot (T-024) | Success measures cannot be evaluated; blocks nothing in the build. |
| D-010 | Hub implementation owner, test URL, delivery date | Open | Academy builds and verifies against the loopback Hub fake. (Was `D-019`.) | Project owner + Hub owner | T-015 integration suite against the real Hub | Blocks live integration only; T-015 is accepted against the fake. |
| D-011 | Navigation source | Confirmed | Owner decision 2026-11-23: Academy owns its sidebar and personal dashboard; it **does not mirror Hub navigation**. Management sections are gated by Academy grants; integrated mode may offer Return to Hub. (Retired D-021.) The old mirrored-menu setting is legacy and must not determine H1 Academy navigation. | Project owner | H1 UI docs and implementation | Existing mirrored-menu configuration must be reconciled; do not claim it has been removed from code. |
| D-012 | Hub ingress model | Defaulted | Option A: Hub reverse-proxies `/academy/*` on the Hub origin; Academy keeps the API-first standalone path. (Was `D-022`.) | Project owner + Hub owner | T-015 | Architecture assumes option A; option B would drop the proxy requirements but keep the adapters. |

### Adopted operational defaults

| ID | Decision | Status | Value / default in force | Owner | Needed by | Impact if still undecided |
|---|---|---|---|---|---|---|
| D-024 | Operational defaults: upload limits, HLS ladder, throttle rates, page sizes, background-task schedule, report columns, notification copy | Defaulted | Values, rationale and the message texts are in `docs/configuration.md`, `docs/background-jobs.md`, `docs/notifications.md` and `docs/reports.md`. Chosen to satisfy REQ-07/REQ-10/REQ-11/REQ-12 without new schema; reversing any value is a one-row change plus a test update. | Tech authority | T-018, T-021, T-022 | The documented values stand; nothing is blocked. |

### H1 product and UX decisions confirmed by the owner

| ID | Decision | Status | Approved H1 value | Owner | Needed by | Implementation caveat |
|---|---|---|---|---|---|---|
| D-026 | H1 operating scope and access | Confirmed | Masheed **only**; one training domain and one personal dashboard; Hub-integrated sign-in without a second Academy login and a simple production standalone local sign-in; trusted Hub-ID-to-local-account linking. No H1 multi-organization administration. | Project owner, 2026-11-23 | H1 documentation | The standalone production path is a target requirement, not verified existing code. |
| D-027 | H1 authorization | Confirmed | `grants_only` in H1; active employees retain `academy.learn`; Academy grants authorize management. Bootstrap the first `academy.admin` via guarded setup; preserve last-admin protection. Old-department-dependent grants suspend for review after department change. | Project owner, 2026-11-23 | H1 documentation | Existing role-plus-grants compatibility tests remain; H1 defaults need deployment verification. |
| D-028 | Academy-local suspension | Confirmed | Only authorized `academy.admin` may suspend/lift Academy access with reason/audit. Suspension is indefinite until manually lifted; stored grants are ineffective but retained. Hub deactivation blocks both modes and cancels unfinished enrollments; Hub reactivation does not revive cancelled rows or override local suspension. | Project owner, 2026-11-23 | H1 documentation | Session-open behavior and enrollment uniqueness are implementation details requiring safe resolution; no speculative extra workflow. |
| D-029 | Linked membership synchronization | Confirmed | Signed Hub webhooks plus hourly reconciliation of **linked users only**, and after reconnection. Directory failure is not proof of deactivation; valid integrated sessions may continue safe learning while sensitive directory-dependent actions wait. | Project owner, 2026-11-23 | H1 documentation | Must align with real Hub contract before production integration. |
| D-030 | H1 UI and delivery boundary | Confirmed | Academy-owned personal dashboard and sidebar, separately gated Training Management and System Management; preserve approved PDF style. Small H1 delivered in short demonstrable increments; advanced analytics, quiz UI, certificates, SaaS features and rare workflows deferred. | Project owner, 2026-11-23 | H1 documentation | Visual mockups for new L1–L4 screens remain to be designed against PDF. |

### Infrastructure

| ID | Decision | Status | Value / default in force | Owner | Needed by | Impact if still undecided |
|---|---|---|---|---|---|---|
| D-025 | Object-storage server for the development stack | Resolved | A MinIO image already present in the local engine (`masheed-academy-minio:2025-10-15`, option (a)) is now used: `.env` sets `ACADEMY_MINIO_IMAGE` to it and `docker-compose.yml` points the `minio` service at it. The image has no `curl`, so its healthcheck was changed to `/bin/true` and the live endpoint is checked from the host. Production storage (D-001) is unaffected. | Project owner | T-018 | The dev stack now runs MinIO on `127.0.0.1:9100` (console `:9101`); bucket creation and upload checks can be exercised once T-018 lands. |

### Repository and publication

| ID | Decision | Status | Value / default in force | Owner | Needed by | Impact if still undecided |
|---|---|---|---|---|---|---|
| D-023 | Repository visibility and publishing the documentation baseline | Confirmed | Owner decision 2026-11-22: the repository **stays public** and publishing is authorized. `origin/main` held only GitHub's placeholder `Initial commit` (`README.md` = `# M_Academy`) with no shared history, so the local history was rebased onto it (`git rebase origin/main`) and `main` was pushed normally: no force-push and no commit destroyed. No repository secret is created — `.github/workflows/ci.yml` carries inline placeholder values only. | Project owner | T-001 step 0 (initial push) | Closed. Pushed commits are public and permanent; every later commit must be assumed public, and secrets stay in the untracked `.env`. |

### UI/schema gaps (previously untracked, now resolved)

These were listed as “model gaps” in `docs/ui/wireframes.md` with no register entry. All are
additive, were adopted as the build default before T-006, and are reversible before T-006
closes. They are part of `docs/domain-model.md`.

| ID | Decision | Status | Resolution in force | Owner | Needed by | Impact if reversed later |
|---|---|---|---|---|---|---|
| D-013 | Course owner department and the “general” option | Defaulted | `Course.owner_department_ref` (nullable opaque string). `NULL` means a general course, editable only by `academy.admin`; otherwise managers with `manage_content` scope on that department may edit it. | Project owner | T-006 | Dropping it later is a reversible migration; reports gain/lose a department filter. |
| D-014 | Course cover image | Defaulted | `MediaAsset.kind` gains `image`; `CourseVersion.cover_media` is a nullable FK. Upload uses the same presigned flow as video. | Project owner | T-006 | Cover can be hidden in the UI without a migration. |
| D-015 | Assignment target “everyone” | Defaulted | `Assignment.target_type` includes `organization` with `target_ref = NULL`; expansion covers every active learner at assignment time plus auto-enrollment on later joins. | Project owner | T-007 | Removing it removes one enum value and one case in target expansion. |
| D-016 | Short lesson summary | Defaulted | `Lesson.summary` (max 300 chars, nullable), shown in the outline. | Project owner | T-006 | Purely additive. |
| D-017 | Recipient-count preview | Defaulted | `POST /manage/assignments/preview/` returns a count only (no identities), capped at 5,000, using the same expansion selector as the real assignment. | Project owner | T-019 | Endpoint can be dropped without schema impact. |

## Legacy ID mapping (retired numbers)

The numbers below appeared in `CHARTER.md` 2.0 and `docs/hub-contract.md` before this
register existed. They are retired and must not be used again.

| Retired | Now | Subject |
|---|---|---|
| D-018 | D-004 | Signed identity token format and rotation |
| D-019 | D-010 | Hub implementation owner and availability |
| D-020 | D-005 | Academy DNS and TLS |
| D-021 | D-011 | Navigation source |
| D-022 | D-012 | Hub ingress model |
| CHARTER 2.0 “D-003” | D-002 | Business time zone |
| CHARTER 2.0 “D-008” | D-003 | Retention periods |
| CHARTER 2.0 “D-009” | D-007 | Supported browsers |
| CHARTER 2.0 “D-010” | D-008 | Brand font and wordmark |

## Verification
- Every `D-NNN` reference in the repository resolves to a row above
  (`grep -rn "D-0[0-9][0-9]" --include=*.md .`).
- No document other than this one states a decision value as its own source of truth.
