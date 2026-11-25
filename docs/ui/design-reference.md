# Design reference register — Official UI/UX v1.0

**Status:** Received and adopted 2026-11-25 (D-045). This file owns the provenance, integrity and
storage of visual references. The design itself is owned by `design-system.md`; screens and gates
by `wireframes.md` and `screen-specification.md`.
**Rule:** the repository tracks **text specifications and tokens only**. Images, boards and design
packages are never committed to this public repository.

## 1. Package identity

| Item | Value |
|---|---|
| Name | `Masheed-Academy-Official-UI-UX-v1.0.zip` |
| Delivered | 2026-11-25 |
| Owner approval | Approved as the official visual and engineering reference (D-045) |
| Archive SHA-256 | `3fefdecc31757389229b1ca8296b40b7991e962b9d94d5b0fc151eb0b9831e30` |
| Size / content | 21,803,111 bytes · 24 files: 10 text/token files + 14 reference PNGs |
| Integrity check | every PNG matches `REFERENCE_INDEX.csv` (SHA-256 and pixel dimensions), verified 2026-11-25 |
| Gates | the package **closes no project or screen-group gate**; each group still needs owner approval |

Text files read and merged: `README.md`, `DESIGN_SYSTEM.md`, `DESIGN_TOKENS.json`, `tokens.css`,
`SCREEN_INDEX.csv`, `SCREEN_SPEC.md`, `REFERENCE_INDEX.csv`, `ACCEPTANCE.md`, `IMPLEMENTATION.md`,
`OWNER_TO_AGENT.md`.

## 2. Reference boards (verified fingerprints)

All files are `1536×1024` except R02 and R05 (`1672×940/941`).

| ID | File | Usage | SHA-256 |
|---|---|---|---|
| R01-public | `R01-public.png` | Public hero only; ignore internal panels | `855525e606e043c99e9db2c027d9c199ed5a8f43e95c394ef4b4c27bdbe8bbac` |
| R02-login | `R02-login.png` | Login layout; no self-registration or SSO | `f8d4a6cfb76c2aa8555ba560fd2609de9f31608a5cb3fad17f608eba461f9bea` |
| R03-recovery | `R03-recovery.png` | Recovery flow only; generic response | `7279c91a59144d8a45a9fc6c9676a09aed457c12209afbffbb82872dc12b61e5` |
| R04-verification-mfa | `R04-verification-mfa.png` | Verification, TOTP and recovery only | `22ef7c7f35215cd64e718a3ed472df3198918392922bfe31773e047ea5e42351` |
| R05-master | `R05-master.png` | **Controlling internal shell**; no banner | `5ae007403a1c972c2742b0a8d2dfe7f52f57e996e9adbb1de3f9ec7c64e50207` |
| R06-platform | `R06-platform.png` | Platform overview and companies | `ab471a952db4b4a94fa27e7465e1acc62a674c9b8c0654ba239ea8491050cdcc` |
| R07-people-rbac | `R07-people-rbac.png` | Employees, departments and role forms | `7e44f0b190290f256a8d2d26dba05bb10bc6c27658e30049dffdc5f21485de7b` |
| R08-company | `R08-company.png` | Company dashboard and training overview | `fcc35cbf903cf9aa537e4a27e76274d90b1f3cfcfed6b684dd4e4f21855d0b77` |
| R09-company-detail | `R09-company-detail.png` | Company detail and managers | `156f5b7ab391ef6f4dc6742283f44804dd3ebf55db84cea9fff0ab91da18e854` |
| R10-department | `R10-department.png` | Department dashboard and assignment list | `2df192be3fb45708d56157920eccee6924a023d47baea7eaf5100891d733ce1d` |
| R11-builder-player | `R11-builder-player.png` | Course builder, assignment form and player | `b5062d71018641fa32340b46d6e67f450b74e421b5d28a3d181a7d3f26d0d93b` |
| R12-reports | `R12-reports.png` | Reports, notifications and settings | `02199c20baba7a7736bf828a73d77065506d4f4350a92b4a4c4798fb498c745b` |
| R13-catalog | `R13-catalog.png` | Course/programme list and assignments | `a18d129a38d4c796d5dcd922e9db7addb2c90856b5e3b0bbb131621a1efeb380` |
| R14-learner | `R14-learner.png` | Learner dashboard and shared screens | `15a71c8b086d02fc207b5ea84b39bbec95101757a846903d6c36b540edd4e45b` |

Boards are **visual intent**, not pixel baselines. Engineering dimensions come from
`design-tokens.json`; screen behaviour from `screen-specification.md`. Sample identities, avatars,
metrics, labels and extra functionality in the boards are never copied into production.

## 3. Storage and restore

| Copy | Location | Tracked |
|---|---|---|
| Original package (owner) | `../_design-archive/official/Masheed-Academy-Official-UI-UX-v1.0.zip` — outside Git, sibling of the repository root | No |
| Local extracted boards | `.design-references/official-ui-ux-v1.0/Masheed-Academy-Official-UI-UX-v1.0/references/` (Git-ignored) | No |
| Text specifications and tokens | `docs/ui/` | Yes |

Restore:

```bash
# from the repository root; the archive is outside the repository
unzip ../_design-archive/official/Masheed-Academy-Official-UI-UX-v1.0.zip \
  -d .design-references/official-ui-ux-v1.0
sha256sum .design-references/official-ui-ux-v1.0/Masheed-Academy-Official-UI-UX-v1.0/references/*.png
# compare with §2; R01 is a valid reference if all 14 hashes match
```

If the archive is lost, ask the owner for the package again; never rebuild a board from a
screenshot or a crop.

## 4. Superseded material (archived, not deleted)

Moved to `../_design-archive/superseded/` and removed from the active repository. Git history is
unchanged; the old PDF and page renders were tracked and their deletion is recorded in this
branch's commit.

| Material | Type | Why superseded |
|---|---|---|
| `Academy-UX-Handoff-v1.0.zip` | Design package | Different Hub/React context; routes, stack and media assumptions not applicable |
| `Masheed-Academy-UX-Batch-1-Review.zip` | Design package | Same; review material only |
| `docs/ui/reference/masheed-academy-screens.pdf` + `pages/page-*.png` | Interim visual reference | Replaced by R01–R14; its sampled palette conflicts with the tokens |
| `.docs-package-backup/` | Local doc backups | Duplicated/older copies of governance and UI docs kept in the project root |
| `INSTALLATION_AR.md` | Superseded document-package note, 2026-11-23 | Installs a retired doc package, cites the old PDF, the single-organization/Hub assumptions and D-026–D-030; was never tracked in Git |

Their interaction and accessibility lessons may be read for context, but their routes, providers,
stack and Hub assumptions must not be revived.

## 5. Gaps and open items for the owner

| Gap | Effect | Handling |
|---|---|---|
| Official Masheed logo and gold geometric element not supplied as standalone files | No final brand mark in UI | Text placeholder until the owner provides the approved asset; never crop the mockup |
| Rubik font binaries (Arabic + Latin) and licence file not supplied | Brand typography cannot be implemented/verified | T-029 keeps the current font as a known gap and does not claim compliance; no substitute brand font is declared approved |
| Licensed architecture photography and approved public copy | Public/auth imagery is placeholder | Owner supplies assets before the public-screen visual sign-off |
| Generated PNGs are not Figma files or pixel measurements | Exact spacing cannot be measured from images | Dimensions from `design-tokens.json`; group approval fixes implementation defaults |
| `SCREEN_INDEX.csv` was written against charter 2.3 and maps screens to provisional tasks | Task mapping may not match the current plan | Reconciled in `wireframes.md`; plan dependencies win |
| Package includes TOTP screens (AUTH-05) while T-027 builds MFA | AUTH-05 must not be implemented before T-027 | T-029 implements the UI only after the backend contract exists |

The current application still ships the T-013 interim stylesheet (Noto Sans Arabic, `#F8FAFC`
canvas). That is a known implementation gap for T-029, not a design reference; this work item does
not change code.

## 6. Preventing conflicting references

1. **One active package.** `Masheed-Academy-Official-UI-UX-v1.0` is the only visual source. A new
   package becomes active only through a new decision in `docs/decisions.md`; the old one is marked
   superseded and archived.
2. **No design binary in Git.** Images, boards, PDFs and packages stay outside the repository or in
   the Git-ignored `.design-references/`. Only text specs and tokens are tracked.
3. **No duplicate specification.** Identity, shell and components live in `design-system.md`;
   screens and states in `screen-specification.md`; reference mapping and group gates in
   `wireframes.md`; provenance and fingerprints here. Other documents link, never restate.
4. **Traceable gates.** Every screen group names its reference and task in `wireframes.md`; an
   implementation task is not eligible without that record.
5. **Fingerprint check.** A reference copy is valid only when all 14 hashes in §2 match; a mismatch
   is reported to the owner instead of being used.
