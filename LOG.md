# LOG — Significant Project Events

> Append-only historical record. Do not silently edit or delete old entries. Correct
> mistakes with a new entry referencing the original.

## Entry template

### [YYYY-MM-DD] — Event title

- **Type:** Milestone | Change | Decision | Release | Incident | Dependency | Verification | Exception
- **Status:** Proposed | Approved | Implemented | Tested | Verified | Merged | Released | Rejected | Superseded
- **Summary:** What happened.
- **Impact:** What changed or is affected.
- **Evidence:** Commit, PR, test report, deployment or other evidence. Required for
  Implemented, Tested, Verified, Merged and Released entries.
- **Approved by:** Required when approval applies.
- **References:** Task, ADR, issue, release, exception record or superseding entry.
- **Corrects:** Optional.

---

## Entries

### [2026-11-22] — Rebuild from scratch with UPDS documentation baseline

- **Type:** Milestone
- **Status:** Approved
- **Summary:** The project restarts from a clean repository governed by UPDS 1.0.0-rc2.
  The seven core documents (README, RULES, STATUS, CHARTER, ARCHITECTURE, LOG, SKILLS)
  were created from the UPDS core templates and seeded with the Masheed_Academy
  requirements: charter scope and REQ-01…REQ-20 condensed from legacy charter 1.3;
  architecture decisions from the legacy design; open decisions D-001…D-009 consolidated;
  a fresh 24-task + gate plan in STATUS; performance targets moved to
  `docs/performance-profile.yaml`. Live requirement references (`hub-contract.md`,
  wireframes, email templates, visual-baseline PDF and renders) were carried into `docs/`.
- **Impact:** Establishes the authoritative documentation interface for the rebuild.
  The legacy repository and its history remain available as reference; none of its
  implementation state is claimed here until re-implemented and verified.
- **Evidence:** This documentation baseline (initial package creation).
- **Approved by:** Project owner
- **References:** UPDS package (external, not vendored) adoption guide section A; legacy LOG.md
  (history, kept in the legacy repository).

### [2026-11-22] — Documentation baseline adopted as starting state

- **Type:** Milestone
- **Status:** Proposed
- **Summary:** Initial UPDS project documentation created; project-specific facts remain
  to be confirmed as implementation starts (env values, exact pinned versions, CI details).
- **Impact:** Defines the documentation baseline for T-001 onward.
- **Evidence:** Initial repository/package creation.
- **Approved by:** Pending
- **References:** UPDS adoption checklist; STATUS.md → Next action (T-001).

### [2026-11-22] — Build specifications completed before T-001

- **Type:** Change
- **Status:** Implemented
- **Summary:** A readiness review of the baseline found four gaps that would have stalled
the build at the schema tasks: scattered/conflicting decision IDs, legacy `P0-/P1-` plan
IDs with no mapping, no field-level schema (and no specification of the anti-skip progress
algorithm), and no API inventory. All four are closed. New canonical documents:
`docs/decisions.md` (D-001…D-017 plus a mapping for the retired D-018…D-022 and four
CHARTER 2.0 collisions), `docs/traceability.md` (ID scheme, legacy→task map, CI gates
G1–G9, REQ→task evidence, sources of truth), `docs/domain-model.md` (entities with fields
and constraints, state machines, invariants, and the normative heartbeat/gating/completion
algorithm in §7), `docs/api.md` (endpoints, capabilities, error codes), and
`docs/adr/README.md` (ADR index and template). CHARTER 2.1 corrects decision IDs with no
scope change; ARCHITECTURE §5/§6 now defer to the canonical specs, §7 gains the audited
action list, §11 numbers ADR-001…ADR-013, §12 maps the plan to task IDs; RULES numbers the
CI gates and fixes the TODO example; STATUS and README point at the new documents;
SKILLS no longer points at unvendored UPDS files; wireframes and hub-contract use current
IDs and resolvable section references.
- **Impact:** Phase 0 tasks T-006…T-008 (schema) and T-011, T-016…T-022 (API) can now be
implemented from documents instead of design decisions made inside code. D-013…D-017 are
now tracked as Defaulted, and no task waits on an open decision.
- **Evidence:** New files committed as documentation; `grep -rn "P0-[0-9]\|P1-[0-9]"
--include=*.md .` returns no matches; every `D-NNN`, `§` and ADR reference resolves.
- **Approved by:** Project owner (requested and authorized this work).
- **References:** `docs/decisions.md`, `docs/traceability.md`, `docs/domain-model.md`,
  `docs/api.md`, ADR-012, ADR-013; next action T-001.

### [2026-11-22] — Rebuild moves to a new repository with an isolated stack

- **Type:** Decision
- **Status:** Approved
- **Summary:** The rebuild will live in its own repository, `M_Academy`, with its own
history and no dependency on the legacy repository, its images, volumes, database, cache,
credentials or containers. The legacy deployment keeps running unchanged and is
reference-only. The new stack is defined as compose project `m-academy` with its own
PostgreSQL, Redis, MinIO buckets, Celery broker, volumes and host ports. While checking the
host, the legacy stack was found to hold `8001` (web), `9000`/`9001` (MinIO) and `8026`
(MailHog); the previously documented `localhost:8001` was therefore wrong for a
side-by-side setup. New bindings were verified free and reserved: web `8101`, PostgreSQL
`5433`, Redis `6390`, MinIO `9100`/`9101`, MailHog `8126`/`1126`.
- **Impact:** README setup, STATUS T-001 acceptance and ARCHITECTURE §8 now reference the
isolated stack. Cookies are namespaced (`m_academy_sessionid`) because browsers scope
cookies by host, not port, and the legacy app runs on the same `localhost`. RULES gained
prohibitions on Docker commands that can reach other projects. CHARTER 2.2 records the
repository and environment constraints without changing product scope. Initial push is
gated on D-023 (repository visibility), because the baseline is internal material.
- **Evidence:** `docker ps`, `docker compose ls` and `netstat` checks recorded in
`docs/operations/environments.md` §3 (legacy `masheed-academy` running; candidate ports
free).
- **Approved by:** Project owner (requested the new repository and full isolation).
- **References:** `docs/operations/environments.md`, D-023, T-001, CHARTER 2.2, RULES.

### [2026-11-22] — Build-blocking gaps closed: configuration, jobs, copy, reports

- **Type:** Documentation
- **Status:** Done
- **Summary:** Four remaining specifications were written so no task has to invent a
number or a sentence: `docs/configuration.md` (core settings, data stores, upload policy,
HLS ladder 360p/720p with 6 s segments, pagination 25/100, throttle table, test-profile
overrides), `docs/background-jobs.md` (eight Celery tasks with queue, schedule, retry and
idempotency key, plus what is deliberately synchronous), `docs/notifications.md` (seven
message types with Arabic and English copy, dedupe keys, suppression and directory-outage
behaviour, built on the approved `docs/ui/emails/escalation-digest.html`), and
`docs/reports.md` (metric definitions, columns for all four report endpoints, UTF-8 BOM
CSV with formula neutralisation, scope rule, query budget).
- **Impact:** `docs/operations/environments.md` gained §8 service targets and alert
thresholds. T-018, T-021, T-022 and T-024 acceptance now cite these files. The defaults are
recorded once as D-024 (Defaulted, cheap to reverse). Traceability and README list the new
canonical files.
- **Evidence:** Every new file is linked from README and traceability; no value contradicts
`docs/performance-profile.yaml` (page size 25, RPO 24 h, RTO 4 h, 200 concurrent viewers)
or the `renditions` example in `docs/domain-model.md` §2.5.
- **Approved by:** Project owner («سدها»).
- **References:** D-024, T-018, T-021, T-022, T-024, `docs/ui/emails/`.

### [2026-11-22] — T-001: repository and isolated stack bootstrapped

- **Type:** Implementation
- **Status:** Implemented (evidence below). Not yet verified in CI: the first push is gated
  by D-023, so the workflow is committed but has not run on GitHub.
- **Summary:** The repository was initialised with its own history (`git init -b main`,
  `origin` = `M_Academy`) and the scaffold added on `task/T-001-scaffold`. Contents: pinned
  `pyproject.toml` (Django 5.2.19, DRF 3.18.3, drf-spectacular 0.30.0, psycopg 3.3.9,
  Celery 5.7.0, redis 8.1.0, boto3 1.44.9, django-storages 1.14.6, gunicorn 27.0.1, plus
  pinned dev tooling), `config` project with `settings/{base,dev,test,prod}.py`
  (`config.settings.prod` as named in `docs/hub-contract.md` §7), `/healthz` checking the
  database and the cache, namespaced cookies from `docs/configuration.md`, a multi-stage-free
  Dockerfile with ffmpeg/ffprobe, the isolated compose file (project `m-academy`, ports
  8101/5433/6390/9100/9101/8126/1126), `.env.example` with every documented variable, a
  generated untracked `.env`, Makefile, pre-commit, the three gate scripts and the nine-job
  CI workflow.
- **Evidence:** `docker compose -p m-academy up -d --build --wait web db redis mailhog worker
  beat` → six services healthy; `curl http://localhost:8101/healthz` → `200` with
  `{"database": true, "cache": true}`; `celery -A config inspect ping` → `pong`, 1 node;
  `ruff check` + `ruff format --check` clean (41 files); `mypy` clean (16 files);
  `makemigrations --check` → no changes; `migrate` applied; `spectacular --validate
  --fail-on-warn` → 0 warnings; `pytest` → 2 passed. Isolation: only `m-academy-*`
  containers started, volumes `m-academy_{media,pgdata,redisdata}` created, network
  `m-academy_default` created, and the legacy `masheed-academy-*` containers stayed `Up`
  untouched. `.env`, `.venv`, `.build.log` and `celerybeat-schedule` are ignored.
- **Blocked:** the object-storage service. `minio/minio` no longer resolves on Docker Hub,
  `ghcr.io/minio/minio` returns denied and `quay.io/minio/minio` returns 401, so
  `m-academy-minio-1` was not started and the bucket step of the isolation checklist is
  unverified. Raise as D-025 (owner decision) rather than substituting a provider silently.
- **Not yet active by design:** G3's 85% threshold and G7's tenant half activate with T-003;
  G8 activates when `tests/e2e/` exists (T-023). Each script prints that state instead of
  reporting a pass.
- **References:** T-001, D-023, D-025, `docs/operations/environments.md` §7,
  `docs/configuration.md`, `.github/workflows/ci.yml`.

### [2026-11-22] — D-023 confirmed: repository stays public, history published

- **Type:** Decision
- **Status:** Approved
- **Summary:** The owner confirmed that `M_Academy` stays **public** and authorized
  publishing. The remote held only GitHub's placeholder `Initial commit` (`README.md` =
  `# M_Academy`) and shared no history with the local repository, so both local branches were
  rebased onto `origin/main` (`git rebase origin/main`, ours kept for `README.md`) and `main`
  was pushed normally — no force-push, no commit destroyed. The project `README.md` supersedes
  the placeholder one.
- **Impact:** The documentation baseline and the T-001 scaffold are on GitHub and the nine CI
  jobs run there. Everything pushed is public from now on, so no secret may enter a tracked
  file and future internal material must be assumed world-readable.
- **Evidence:** `git rebase origin/main -X theirs` on `main` left a tree identical to the
  pre-rebase baseline; the same on `task/T-001-scaffold` left a tree identical to the
  pre-rebase T-001 commit (`git diff --stat 24e7b71` empty). Push and CI receipts are in the
  checkpoint report.
- **Approved by:** Project owner (2026-11-22): stays public, proceed as is; path = rebase
  then normal push.
- **References:** D-023, T-001, `docs/operations/environments.md` §1.

### [2026-11-22] — Record-keeping defects corrected (no earlier entry edited)

- **Type:** Change
- **Status:** Implemented
- **Summary:** A consistency review of the documentation found four defects in the record:
  two LOG entries use a type or status outside the lists in RULES, `CHARTER.md` §10 and
  `docs/configuration.md` §7 attributed retention to the wrong decision, STATUS omitted D-025
  from its open list while calling it a blocker elsewhere, and `docs/skills/closing.md` cited a
  sync table that did not exist.
- **Impact:** Nothing was deleted or rewritten (append-only). The two superseded entries keep
  their text and are corrected here; retention is D-003; `RULES.md` now carries the document
  sync table, the definition of done, the commit-message format, the UI rules and the
  dependency policy that other documents were already referring to; `ARCHITECTURE.md` §7 gained
  an explicit tenant-isolation statement; `docs/traceability.md` §3 gained the gate activation
  column that records which gates are live at each task.
- **Evidence:** `python scripts/check_docs.py` passes; the corrected references resolve to
  `docs/decisions.md` rows D-003 and D-008; every rule referenced by `docs/skills/closing.md`
  now exists under that name.
- **Corrects:** `[2026-11-22] Documentation baseline adopted as starting state` (Status
  `Proposed`, `Approved by: Pending`) and `[2026-11-22] Build-blocking gaps closed:
  configuration, jobs, copy, reports` (Type `Documentation`, Status `Done`).
- **Approved by:** Project owner (2026-11-22: «أصلح كل ما سبق»).
- **References:** RULES (LOG status values, Document sync table, Definition of done, Commit
  messages, UI and frontend rules, Dependencies), CHARTER §10, `docs/configuration.md` §7,
  `docs/decisions.md` D-003, `docs/traceability.md` §3, `docs/skills/closing.md`.

### [2026-11-23] — G6: the image's setuptools finding (CVE-2025-47273)

- **Type:** Fix
- **Status:** Implemented
- **Summary:** G6's image scan was the only red gate. The report showed a single
  finding — setuptools 70.3.0 in `python:3.12-slim`, CVE-2025-47273, fixed in 78.1.1 — with
  Debian at zero and every other Python package clean. Upgrading setuptools inside the image
  did not clear it, and nothing in the app or its runtime dependencies imports either
  setuptools or pip, so the package and its leftovers are now removed from the image after
  the dependency install. A build-time assertion fails the image build if a later change
  brings it back, so the finding cannot reappear silently.
- **Impact:** The production and development images no longer ship build tooling. `pip install`
  still works during the build because it uses build isolation. The gate keeps its severity,
  `--ignore-unfixed` and exit-code rules: nothing was waived or narrowed.
- **Evidence:** The image rebuilt from the same commit with `--no-cache --pull` contains no
  `setuptools`, `pkg_resources` or `_distutils_hack` path outside pip's own vendored copy, and
  `pip list` reports `pip==26.3` only; `pip uninstall` left no dist-info behind. All 83
  Python packages in that image return zero advisories from the OSV API, and the repository
  contains no secret patterns the scanner looks for.
- **Approved by:** Project owner (2026-11-23): fix G6 before continuing.
- **References:** T-001, `docs/traceability.md` §3 G6, `Dockerfile`.
