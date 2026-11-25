# STATUS — Current Project State

> Current state only. Historical detail belongs in `LOG.md`.
> Task definitions and acceptance criteria live in `docs/plan.md`.

**Last updated:** 2026-11-25 (T-035 design reference adoption, in review)
**Updated by:** AI agent (T-035), under the owner's delegation
**Current phase:** H1.5 — Foundation (GATE-1)
**Project scale:** Medium (design envelope: 10 companies / 5,000 users)
**Sensitivity:** Sensitive
**Overall status:** Active — T-025 is merged; T-035 (official UI/UX reference adoption and repository hygiene) is complete on its task branch and awaits owner approval; T-026 CP1 has not started; no application code changed

## Snapshot
`main` carries the working H1 foundations: T-001…T-022 are implemented and tested (590 tests at
the T-022 merge; gates G1–G9 green on their merge commits), with two exceptions recorded below:
T-001's bucket evidence and T-013's English/accessibility completion. The code is still
**single-company** (fixed `ACADEMY_ORGANIZATION_ID`, opaque `user_ref`/`department_ref`) and its
production identity path is Hub-oriented; that is the gap T-026…T-033 close.

The canonical target is now charter 2.5: standalone-first, multi-company, **one company membership
per account**, local identity and dynamic scoped RBAC, with the Hub integration dormant and
optional. Mobile First and the binding visual-reference gate are recorded in D-044. T-025 rewrote the charter,
architecture, rules, decisions, access control, security, domain model, API, configuration,
plan, traceability, UI, notifications, reports, jobs, Hub contract, operations, performance,
migration, README, skills and ADRs to make «كمل» sufficient. The architecture correction removed
the company chooser/switcher and multi-membership paths, added `UNIQUE (user_id)`, platform-only
administration and the capability-preservation matrix, and fixed the evidence policy. **No code,
template, migration, API contract, Hub activation, infrastructure or dependency changed in T-025.**
T-025 is merged as `b592498` (CI run 45687216183, success); implementation starts at T-026.

## Active work
| ID | Task | Status | Owner | Depends on | Acceptance / evidence |
|---|---|---|---|---|---|
| T-025 | Documentation and governance consolidation | `[x]` — merged in `b592498`; CI success 45687216183 | AI agent; owner approved 2026-11-25 | owner approval | `docs/plan.md` §4 T-025; `check_docs` green (38 files); 23-row capability matrix |
| T-035 | Official UI/UX reference adoption and repository hygiene | `[~]` — branch `task/T-035-design-reference-adoption`, content commit `165d261`, CI success 45692372567; owner approval and merge pending | AI agent; docs only | T-025 | `docs/plan.md` §4 T-035; `docs/ui/design-reference.md`; `check_docs` 41 files |
| T-026 | Tenancy and account foundation | `[ ]` next — do not start without «كمل» | AI agent | T-025 | `docs/plan.md` §4 T-026, CP1–CP3 |
| T-033 | Hub quarantine | `[ ]` after T-026 closes | AI agent | T-026 | `docs/plan.md` §4 T-033; never before T-026 `[x]` |
| T-001 | Repository and stack bootstrap | `[~]` — bucket step evidence outstanding | Tech authority | — | `docs/operations/environments.md` §12 step 7 |
| T-013 | UI foundation | `[~]` — extended by T-029 | Tech authority | T-002 | en catalogue + axe evidence land in T-029 |
| T-023 | Learner + management UI (old scope) | `[–]` superseded by **T-031** | — | — | historical only |
| T-024 | Hardening + E2E + ops (old scope) | `[–]` superseded by **T-034** | — | — | historical only |
| GATE-1 | H1.5 gate | `[ ]` | Project owner | T-025…T-034 | `docs/plan.md` §5; capability matrix verified |

Completed: T-002…T-012, T-014…T-022 on `main` with their CI/LOG evidence. T-015 is completed code
that T-033 will quarantine; T-016/T-009 are completed v1 engines that T-028 replaces.

## Recently completed
- 2026-11-25 — **T-035 in review (docs only).** The owner's official
  `Masheed-Academy-Official-UI-UX-v1.0` was verified (14/14 board fingerprints and dimensions), its
  text specifications and tokens were merged into `docs/ui/`, and it is now the single design
  authority (D-045). The superseded `Academy-UX-Handoff-v1.0` and `Masheed-Academy-UX-Batch-1-Review`
  packages, the interim PDF/page renders and the local document backup were removed from the active
  tree and archived in `../_design-archive/`; boards are Git-ignored and no design binary is
  tracked. Mobile First, the six verification widths (320/390/768/1024/1440/1920) and the master
  shell are permanent in `RULES.md` and `docs/ui/design-system.md`. No screen group gate was closed,
  and no code, template, stylesheet, migration, API or dependency changed. Content commit `165d261`
  passed CI run 45692372567; `check_docs` G9 passed (41 files); every board hash matched.
- 2026-11-25 — T-025 H1.5 amendment: one company membership per account with `UNIQUE (user_id)`,
  no company chooser/switcher/selection APIs or screens, platform administration without a
  membership, D-043/D-044 and the capability-preservation matrix; Mobile First at 390/768/1440
  with 320+ testing and the binding visual-reference gate. Prior package commits `96f78d2`,
  `eb19fd1`, `15e0e53`, content amendment `e2e9c1b`; the capability matrix was completed to
  **23 rows** with company administration restored. Owner approved the architecture and merge on
  2026-11-25. Final branch head `e19f76c` passed CI run 45686699559; merge commit `b592498`
  passed CI run 45687216183; `check_docs` G9 passed (38 files). T-025 is closed.
- 2026-11-25 — T-022 reports: one selector module defines every number, department scope includes
  general courses and refuses a cross-department read, streamed BOM CSV with formula-safe cells
  and an audited export. See `LOG.md`.
- 2026-11-25 — T-021 notifications: seven ar/en messages through a durable queue, −3/0/+1
  reminders, due+3 manager digest, suppression codes and a repair sweep. See `LOG.md`.
- 2026-11-25 — T-020 heartbeat/completion: server-credited elapsed window, forward-skip refusal,
  idempotent completion and named blockers. See `LOG.md`.
- 2026-11-25 — T-019 assignments: one expansion selector, membership-driven enrol/cancel,
  server-enforced lesson lock. See `LOG.md`.
- 2026-11-25 — T-018 media: presigned tenant-key uploads, `stat` verification, ffmpeg→HLS and
  poster/playlists. See `LOG.md`.
- 2026-11-25 — T-017 content services; T-016 permission grants; T-015 Hub HTTP integration;
  T-014 sessions/auth lifecycle; T-013 UI foundation; T-012 append-only audit; T-011 API
  skeleton; T-010 test foundations; T-009 authorization v1; T-008…T-006 schema. See `LOG.md`.

## Blockers and risks
| Item | Impact | Owner | Next action | Review |
|---|---|---|---|---|
| D-001 production storage provider | Blocks production media only; dev/test use MinIO | Project owner | Decide before the production release decision | T-034 |
| D-005 production domain/TLS owner | Blocks production ingress only | Project owner + ops | Decide before production deploy | T-034 |
| D-009 KPI values | Blocks success measurement, not the build | Project owner | Set before the pilot | T-034 |
| T-001 bucket evidence | Holds T-001 `[~]` | Tech authority | Re-run the bucket check with the resolved MinIO image | T-034 |
| Legacy identity mapping file (`legacy_user_ref,email,display_name`) | T-026 cannot activate real accounts without it | Project owner/HR | Provide a verified file before T-027 | T-026/T-027 |
| Two stacks on one host | Port/volume/cookie collision or legacy damage | Tech authority | Isolation rules enforced; only `m-academy-*` commands | ongoing |
| Public repository (D-023) | Leaking internal material | Project owner | No secrets in tracked files; assume every commit is public | ongoing |
| Hub contract (D-004/D-010) | No H1.5 impact; Hub dormant | Project owner + Hub owner | Revisit only at a reactivation decision | H2 |

## Decisions
Single register: [`docs/decisions.md`](docs/decisions.md). This file does not duplicate values.
- **Open:** D-001, D-005, D-009, D-010 (deferred H2).
- **Confirmed (2026-11-25):** D-031…D-044 (standalone/Hub dormant, tenancy, local identity, RBAC,
  public origin, mail, PII, settings, observability, environments, UUID strategy, outbox deferral,
  performance profile, one membership per account, Mobile First and visual reference). Older
  confirmed decisions remain unless marked superseded.
- **Resolved:** D-025 (local MinIO image).
- **Superseded:** D-002→D-038, D-013/D-026→D-032, D-027→D-034; ADR-002/010/011/012/014 replaced by
  ADR-023…026.
- Retired numbers (D-018…D-022, ADR numbers 15–22) are mapped in the register and must not reappear.

## Next action
**T-035 is in review**: the branch is pushed and CI evidence is recorded in `LOG.md`. The owner
should review the package adoption, archive and permanent UI rules and approve the merge to `main`.
After that merge, **T-026 CP1** (tenancy schema expand) is the next eligible checkpoint, exactly as
`docs/plan.md` §4 defines it, but it has **not** started. T-033 remains `[ ]` and may start only
after T-026 is `[x]`, in parallel with T-027/T-028; T-026 CP1 alone is not sufficient. D-001, D-005
and D-009 remain open. Screen groups remain **pending owner approval**; the official logo, Rubik
binaries and licensed photography are still missing assets. Say «كمل» after T-035 is merged to
authorize T-026 CP1.

## Update rules
- Update when project state changes. Do not turn this file into a diary (`LOG.md` owns history).
- `[x]` requires a commit, a CI run and named evidence. Do not mark work complete because code
  exists locally.
- Keep task IDs and states consistent with `docs/plan.md` and `docs/traceability.md`.
