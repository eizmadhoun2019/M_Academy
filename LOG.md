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

### [2026-11-23] — G6 verified green: the finding came from pip's bundled SBOM

- **Type:** Fix
- **Status:** Verified
- **Summary:** The remaining red gate was not the image's own content. CI runs each step as
  `bash -e`, so the failing trivy pipeline ended the step before any diagnostics ran; once
  the exit code was captured and re-raised, the step reported `setuptools` /
  `CVE-2025-47273` while the image contained no such package and the build assertion proved
  it could not be imported. The step then named the matching files: the only declaration of
  setuptools 70.3.0 was `pip/_vendor/bom.cdx.json`, the bill of materials that ships inside
  pip and that trivy reads as a source of truth (hence its own warning about third-party
  SBOMs). The runtime image needs no installer, so pip and setuptools are both removed after
  the dependency install; the build fails if either is importable again.
- **Impact:** The gate keeps its severity, `--ignore-unfixed` and exit-code rules — nothing was
  waived, narrowed or silenced, and no exception record was needed. A failing scan now explains
  itself in a run annotation that anyone can read without an account.
- **Evidence:** CI run `45138282623` on `main` (commit `076af2d`): ten jobs, nine success, one
  skipped by design (g8-e2e, guard), **G6 security green**; `python scripts/check_docs.py`
  passes.
- **Approved by:** Project owner (2026-11-23): «اصلح كل ما سبق وبعدها نعودلحسم مشكلتنا ci:g6».
- **References:** T-001, `docs/traceability.md` §3 G6, `Dockerfile`, `.github/workflows/ci.yml`.

### [2026-11-23] — T-002: settings profiles, Celery queues, JSON logging, i18n

- **Type:** Feature
- **Status:** Implemented
- **Summary:** The Celery app now has the queue topology its catalogue assumes: `default`,
  `media` and `notifications` are declared explicitly, `academy.media.*` routes to `media`,
  `academy.notifications.*` and `academy.escalations.*` to `notifications`, and anything else —
  including a misnamed task — to `default`, with implicit queue creation off so a typo cannot
  open a queue no worker reads. The beat schedule stays with the tasks it names
  (`docs/background-jobs.md` §4), because scheduling a task that does not exist yet would only
  fill queues with unroutable messages. Logging is one JSON object per line
  (`config/logging.py`) with a request id that `RequestIdMiddleware` takes from an
  `X-Request-ID` header only when it is short and safe, generates otherwise, and echoes back.
  `LocaleMiddleware` is installed in Django's required order, the default language `ar` is
  validated against the supported list, and the language cookie is `django_language`.
- **Impact:** Every process logs machine-readable lines with a traceable request id; a task name
  is routed by code rather than by whoever typed the worker command. No new environment
  variable was introduced, so `docs/configuration.md` §1–§9 is unchanged; its new §10 documents
  the log fields and the header.
- **Evidence:** `tests/test_settings.py` (26 tests overall in the suite) covers the routing of
  every documented task name, the default-queue fallback, the declared queue set, `ping`
  returning `pong`, a real publish through this project's Redis broker landing on `default`
  (probe on a spare database so the development worker cannot consume it first), the JSON
  fields, request-id validation and echo, the Arabic default, English availability, locale
  middleware order, the cookie switching the active language, and the production profile
  refusing a missing `ACADEMY_ALLOWED_HOSTS` or a short `DJANGO_SECRET_KEY` while loading with
  the required values. Locally `ruff check`, `ruff format --check`, `mypy .` and `pytest -q`
  pass; `python scripts/check_docs.py` passes.
- **Approved by:** Project owner (2026-11-23): «كمل» after G6 went green.
- **References:** T-002, `docs/configuration.md` §10, `docs/background-jobs.md` §1–§4,
  `docs/operations/environments.md` §4, `config/settings/base.py`, `config/celery.py`.

### [2026-11-23] — T-002 merged to main

- **Type:** Feature
- **Status:** Merged
- **Summary:** The owner merged `task/T-002-settings` into `main` (fast-forward, no rewrite) at
  the owner's instruction «ادمج», so the queue routes, the JSON log format and the locale
  middleware are now part of the mainline rather than a branch.
- **Impact:** `main` carries the settings work; the status row moved from review to done.
- **Evidence:** `main` = `8168477`; CI run `45141974756` green on that exact commit (g1–g7 and
  g9 pass, g8-e2e skipped by its guard); `python scripts/check_docs.py` passes.
- **Approved by:** Project owner (2026-11-23): «ادمج ثم كمل».
- **References:** T-002, `STATUS.md`, `config/settings/base.py`.

### [2026-11-23] — T-003: academy skeleton (tenant base model, adapter loader, exceptions)

- **Type:** Feature
- **Status:** Implemented
- **Summary:** The `academy` package now exists as a Django app with the three pieces every
  later task builds on. `TenantModel` (abstract) carries the documented shared columns —
  UUID primary key generated in Python, a plain `organization_id` UUID (never a foreign key,
  because the organization lives in the Hub), and the two timestamps — plus a `for_org`
  manager that refuses anything that is not an organization UUID, so an unscoped read is a
  failing test rather than a global query. `academy.adapters.loader` resolves each host seam
  from an `ACADEMY_ADAPTER_*` `module:Class` value, caches it, and raises on an unknown,
  unset, malformed or non-class path instead of substituting a default. `academy.exceptions`
  defines the base error with the stable wire code and the four shapes services will raise
  (validation, not found, forbidden, conflict; adapters add "unavailable").
- **Impact:** Gate G7 is now real work: `academy/` exists, so the import boundary inspects
  every module, and `tests/test_import_boundary.py` runs the same script CI runs and proves it
  fails on a planted host import — a green gate can no longer mean "nothing was checked".
  Four new environment variables are documented in `docs/configuration.md` §11 and listed in
  `.env.example`; empty values are valid and mean "not configured".
- **Evidence:** `tests/test_tenant_model.py` (abstract columns, Python-side UUID, default
  manager, `for_org` returns only its organization while the unscoped manager still sees every
  row, `for_org` rejects `None`/str/int), `tests/test_adapter_loader.py` (resolution, caching,
  reset, unconfigured seam per name, unknown seam, five malformed configurations),
  `tests/test_import_boundary.py` (gate active, passes on the tree, detects a planted
  violation). Locally: 47 tests pass, `ruff check`, `ruff format --check`, `mypy .` and
  `makemigrations --check --dry-run` clean; `python scripts/check_docs.py` passes.
- **Approved by:** Project owner (2026-11-23): «ادمج ثم كمل ثم نظف جذر المشروع».
- **References:** T-003, `docs/domain-model.md` §1.1,
  `ARCHITECTURE.md` §4,
  `docs/configuration.md` §11, `docs/traceability.md` §3 G7, `academy/`.

### [2026-11-23] — T-003 merged to main

- **Type:** Feature
- **Status:** Merged
- **Summary:** The owner merged `task/T-003-academy-skeleton` into `main` (fast-forward, no
  rewrite) on the standing instruction «ادمج ثم كمل», so the tenant base model, the adapter
  loader and the domain exceptions are mainline rather than a branch.
- **Impact:** `main` carries the T-003 skeleton; the status row moved from review to done.
- **Evidence:** `main` = `3b7d450`; CI run `45154163445` green on that exact commit
  (g1–g7 and g9 pass, g8-e2e skipped by its guard); `python scripts/check_docs.py` passes.
- **Approved by:** Project owner (2026-11-23): «ادمج ثم كمل».
- **References:** T-003, `STATUS.md`, `academy/models/base.py`, `academy/adapters/loader.py`.

### [2026-11-23] — T-004: the four host seams, their stubs and their contract suites

- **Type:** Feature
- **Status:** Implemented
- **Summary:** The host boundary is now specified as code instead of prose. `academy.adapters`
  holds four `Protocol`s — `IdentityAdapter.verify(token, keys)`, the six directory reads of
  `OrganizationAdapter`, `NotifyAdapter.send_mail/record_activity`, and
  `StorageAdapter.presign_put/presign_get/stat/delete_prefix` — with stdlib-only value types
  (`Department`, `DirectoryUser`, `Role`, `MailMessage`, `MailReceipt`, `ActivityEvent`,
  `ObjectStat`). Two rules are enforced at the seam rather than left to each caller: storage
  keys must sit under `org/<organization_id>/media/` with no traversal and deletion only at a
  directory boundary, and a notification carries an opaque `recipient_ref` with channels from
  `docs/notifications.md` and a Hub-origin-relative link. `host_stub/` implements all four for
  development and tests: HMAC-SHA256 identity with a token signer, an in-memory directory that
  expands department descendants and hides inactive memberships, a recording transport that
  deduplicates by idempotency key and event id (conflicting reuse raises `Conflict`), and an
  in-memory bucket with `put`/`get` helpers. The development and test profiles now default the
  empty `ACADEMY_ADAPTER_*` values to those stubs, so a fresh clone runs with no Hub and no
  bucket while production still fails loudly on the first call.
- **Impact:** REQ-02's evidence now exists: one contract suite per seam under `tests/contracts/`
  (adding an implementation to `IMPLEMENTATIONS` runs the whole suite against it), plus a
  wiring test that loads every seam through `load_adapter` in the test profile and checks the
  instance against its `Protocol`. T-015's Hub transports and T-018's bucket implementation
  plug in without touching callers. `docs/configuration.md` §11 records the stub defaults and
  the acceptance rule.
- **Evidence:** `pytest -q` → 123 passed (76 new); `ruff check`, `ruff format --check`, `mypy .`
  and `makemigrations --check --dry-run` clean; `python scripts/check_docs.py` passes. The
  suites cover signature, key-ring rotation, tampering, malformed tokens, unknown organization
  isolation, descendant membership, the 50-reference batch cap, idempotent mail and activity
  delivery, conflicting key reuse, presign lifetime, key traversal and prefix-delete scope.
- **Approved by:** Project owner (2026-11-23): «كمل».
- **References:** T-004, REQ-02, `ARCHITECTURE.md` §4/§6, `docs/configuration.md` §11,
  `docs/hub-contract.md` §2–§3, `docs/notifications.md` §1, `academy/adapters/`, `host_stub/`.

### [2026-11-23] — T-004 merged to main

- **Type:** Feature
- **Status:** Merged
- **Summary:** The owner merged `task/T-004-adapters` into `main` (fast-forward, no rewrite) on
  the standing instruction «كمل», so the four host-seam Protocols, the development stubs and
  their contract suites are mainline.
- **Impact:** `main` carries the adapters; T-005 can build on them and T-015/T-018 have their
  acceptance suites in place.
- **Evidence:** `main` = `928e7da`; CI run `45159847845` green on that exact commit (g1–g7 and
  g9 pass, g8-e2e skipped by its guard); `python scripts/check_docs.py` passes.
- **Approved by:** Project owner (2026-11-23): «كمل».
- **References:** T-004, REQ-02, `academy/adapters/`, `host_stub/`, `tests/contracts/`.

### [2026-11-23] — T-005: domain events dispatched only after commit

- **Type:** Feature
- **Status:** Implemented
- **Summary:** `academy.events` is the write path's event vocabulary. A service builds a event
  with `emit_on_commit(name, organization_id=…, actor_ref=…, payload=…)` inside its transaction;
  the event is queued through `transaction.on_commit`, so it fires once the outermost
  transaction commits and never at all when that transaction rolls back. The envelope
  (`DomainEvent`) is frozen, carries a generated `event_id` and a UTC `occurred_at`, and its
  payload is validated as JSON-serializable because the same shape is the Celery argument.
  Handlers subscribe by name (`subscribe`/`unsubscribe`/`handlers_for`), are called in
  subscription order through one module-level receiver, and a handler that raises is logged
  with the event name and id while the remaining handlers still run — a committed fact cannot
  be undone by a broken listener, and a post-commit failure must not surface as a failed write.
  Task-enqueueing handlers stay with the tasks they enqueue (T-018, T-021), so nothing schedules
  a task that does not exist yet.
- **Impact:** REQ-04's event half has its evidence; the service skill's step 4
  (`emit_on_commit`) is now executable code. Audit immutability (the other half of REQ-04) is
  T-012.
- **Evidence:** `tests/test_events.py` (22 tests) proves the event waits for the outermost
  commit, a rollback dispatches nothing, an event outside a transaction is dispatched
  immediately, every subscriber receives it in order, unrelated names are not called,
  unsubscribing stops delivery, a failing handler is logged without blocking the next, a
  handler may emit a follow-up event, the envelope is frozen with an immutable payload, and the
  name/actor/organization/payload/timestamp validations hold. `pytest -q` → 145 passed;
  `ruff check`, `ruff format --check`, `mypy .` and `makemigrations --check --dry-run` clean;
  G7 and G9 pass.
- **Approved by:** Project owner (2026-11-23): «كمل».
- **References:** T-005, REQ-04, ADR-007, `docs/skills/service.md` step 4, `ARCHITECTURE.md` §4,
  `academy/events/`.

### [2026-11-23] — T-005 merged to main

- **Type:** Feature
- **Status:** Merged
- **Summary:** The owner merged `task/T-005-events` into `main` (fast-forward, no rewrite) on
  the standing instruction «كمل», so the on-commit emitter and the handler registry are
  mainline.
- **Impact:** Services can emit events from inside their transactions; T-018 and T-021 add their
  task-enqueueing handlers against a stable emitter.
- **Evidence:** `main` = `0204cac`; CI run `45162780071` green on that exact commit (g1–g7 and
  g9 pass, g8-e2e skipped by its guard); `python scripts/check_docs.py` passes.
- **Approved by:** Project owner (2026-11-23): «كمل».
- **References:** T-005, REQ-04, ADR-007, `academy/events/`.

### [2026-11-23] — T-006: catalog schema (Course, CourseVersion, Section, Lesson, MediaAsset)

- **Type:** Feature
- **Status:** Implemented
- **Summary:** The catalog of `docs/domain-model.md` §2.1–§2.5 now exists as a migration. Every
  entity is a `TenantModel`; the documented rules live in the database rather than in the
  promise of a future service: status enums with `CheckConstraint`s, non-blank titles,
  positive positions, `required_watch_percent` between 50 and 100, the `pdf`-needs-a-body rule,
  `UNIQUE(course, version_number)`, the partial unique index that allows at most one
  `published` version per course (with `published_at`/`published_by_ref` required by a check),
  the partial `(organization_id) WHERE status='published'` index, and the media rules
  (`ready` needs a `storage_key`, a `ready` video needs a positive duration, `failed` needs an
  `error_code`). Section and lesson positions use `UNIQUE ... DEFERRABLE INITIALLY DEFERRED` so
  a reorder can move several rows in one transaction, and the two freeze rules are PostgreSQL
  triggers: `courseversion_immutable` (a published version keeps its content, only
  `published → archived`, and an archived version never returns) and `version_content_frozen`
  (inserts, updates and deletes under a published version are refused for sections and
  lessons).
- **Impact:** T-007, T-017, T-018 and T-019 build on a schema whose invariants cannot be
  bypassed by a script, a shell or a second writer. `academy/models/base.py` now binds the
  tenant manager per model (`TenantManager[Course]`) so the type checker keeps model precision
  and still reports any read that bypassed `for_org`.
- **Evidence:** `python manage.py migrate` → `Applying academy.0001_initial... OK`;
  `python manage.py migrate academy zero` → `Unapplying academy.0001_initial... OK`; then
  forward again OK (triggers drop and recreate with the tables). `tests/test_catalog_models.py`
  (26 tests) writes the rows each rule forbids — blank titles, unknown statuses, version 0,
  duplicate version numbers, a second published version, an unstamped publish, position 0,
  duplicate positions (checked with `SET CONSTRAINTS ... IMMEDIATE`), out-of-range watch
  percent, unknown content types, a PDF without body, a `ready` asset without a key, a `ready`
  video with zero duration, a `failed` asset without an error code — and proves the freeze
  triggers reject content changes, inserts and deletes on published versions while drafts stay
  editable. `pytest -q` → 171 passed; `ruff check`, `ruff format --check`, `mypy .` (51 files)
  and `makemigrations --check --dry-run` clean; G7 and G9 pass.
- **Approved by:** Project owner (2026-11-23): «كمل».
- **References:** T-006, REQ-03, `docs/domain-model.md` §2.1–§2.5, §4–§5,
  `academy/models/catalog.py`, `academy/models/media.py`, `academy/migrations/0001_initial.py`.

### [2026-11-23] — T-006: g2 found a type-checker-only defect on a clean interpreter

- **Type:** Fix
- **Status:** Verified
- **Summary:** The first T-006 push failed gate G2 while the same `mypy .` passed in the
development image. The error was reproducible only from a clean `python:3.12-slim` with a fresh
`pip install ".[dev]"`: `Cannot override class variable ... with instance variable [misc]` on
every `objects: TenantManager[Model]` line. The abstract base declared `objects` as a bare
class attribute while the concrete models re-declare it as an annotated instance variable; the
type checker refuses that mix once the model's own annotation is present. The base now declares
`objects: Any = TenantManager()` with a comment, which is the declaration the per-model
overrides require.
- **Impact:** G2 is green again. The lesson is recorded because the development image had
  already installed the package and did not reproduce it, so an image-local green is not
  evidence for G2 — the clean-interpreter run is.
- **Evidence:** CI run `45168784765` (failed, g2) and run `45173786647` (green on
  `9deb22e`, all jobs except the by-design skipped g8-e2e); the clean-room reproduction printed
  the six errors at `academy/models/{media,catalog}.py` and `tests/test_tenant_model.py`.
- **Approved by:** Project owner (2026-11-23): «كمل».
- **References:** T-006, `docs/traceability.md` §3 G2, `academy/models/base.py`.


### [2026-11-23] — Documentation: H1 target adopted selectively (charter 2.3)

- **Type:** Documentation
- **Status:** Approved
- **Summary:** The project owner supplied a complete documentation package (charter,
  architecture, LOG, decision register, Hub contract, UI wireframes plus a new screen
  specification). Its product content was reviewed line by line and adopted **selectively**:
  charter 2.3 records the H1 target (Masheed only, one record set with Hub-integrated or
  standalone local sign-in, `grants_only`, Academy-owned dashboard and sidebar), decisions
  D-011 and D-026…D-030 are confirmed, `docs/ui/screen-specification.md` joins the repository,
  and the Hub contract, wireframes and configuration/API/schema/job documents were aligned.
  The package's replacement copies of `LOG.md` and `ARCHITECTURE.md` were **not** adopted:
  they carried a different history and renumbered ADR-001…ADR-018 with different meanings,
  which would have invalidated the references in `docs/adr/`, `docs/domain-model.md`,
  `docs/configuration.md` and `academy/adapters/organization.py`. `INSTALLATION_AR.md` stays
  outside the repository: it is the package's delivery note.
- **Impact:** Documents now describe the H1 product target truthfully as a target. No code,
  migration, endpoint or screen exists for `grants_only`, the standalone mode or
  `AccessSuspension`; T-009, T-014 and T-016 carry that work. No task status was changed by
  this documentation commit.
- **Evidence:** `python scripts/check_docs.py` (G9) passes locally and in CI run `45343579760`
  on commit `fd464be` (branch `docs/h1-alignment`), where g1–g7 and g9 are green and the g8
  journey job is skipped until T-023 activates it. Relative links, retired identifier
  patterns and required documents were re-checked. No test asserts any of the new product
  text.
- **Approved by:** Project owner (2026-11-23), after reviewing the conflicts above.
- **References:** CHARTER §§1, 3.1, 4, 5; ARCHITECTURE §§7, 11; `docs/decisions.md`
  D-011, D-026…D-030; `docs/ui/screen-specification.md`; `docs/domain-model.md` §2.7, §2.15.

### [2026-11-23] — H1 documentation alignment merged to main

- **Type:** Documentation
- **Status:** Merged
- **Summary:** The owner instructed «ادمج». `docs/h1-alignment` was fast-forwarded into
  `main` (no force-push, no rewritten history) and pushed. Charter 2.3, decisions D-011 and
  D-026…D-030, `docs/ui/screen-specification.md` and the aligned architecture, API,
  configuration, schema, job, Hub-contract, wireframe and traceability documents are now on
  `main`.
- **Impact:** Documentation only. No task status changed; T-009, T-014 and T-016 carry the
  implementation of `grants_only`, the access modes and `AccessSuspension`.
- **Evidence:** CI run `45345097262` on `main` at commit `fa75e87` — g1–g7 and g9 green, g8
  journey job skipped until T-023 activates it.
- **Approved by:** Project owner (2026-11-23): «ادمج».
- **References:** T-001 merge discipline (ff-only), `docs/traceability.md` §3.

### [2026-11-24] — T-007: assignment, enrollment and progress schema

- **Type:** Feature
- **Status:** Implemented
- **Summary:** `academy/models/progress.py` adds the four §2.6–§2.9 tables. `Assignment` carries
  the one-target shape with a `CHECK` that ties `target_ref` to `target_type` and an active-only
  unique index over `(organization_id, course, target_type, COALESCE(target_ref, ''))`, so the
  organization target collides too. `Enrollment` pins a learner to a version and allows exactly
  one active row per learner and course, while a cancelled row leaves room for a new
  enrollment after reactivation. `LessonProgress` keeps one row per lesson with the merged
  ranges in `jsonb` and `CHECK`ed non-negative numbers that cannot exceed the last accepted
  position. `CompletionRecord` snapshots course and version ids and is made immutable by the
  `completion_record_immutable` trigger created in the migration.
- **Impact:** The schema half of REQ-03 and REQ-09 now exists; the heartbeat, gating and
  completion services (T-019, T-020) have their tables and the database enforces their
  invariants. No endpoint or service writes these tables yet.
- **Evidence:** `tests/test_progress_models.py` (25 tests) writes the forbidden row for every
  check and partial index, including a cancelled assignment freeing its target, the
  organization target being unique, a cancelled enrollment allowing re-enrollment, and the
  trigger rejecting both `UPDATE` and `DELETE` on a completion row. `pytest -q` → 196 passed;
  `ruff check`, `ruff format --check`, `mypy .` and `makemigrations --check --dry-run` clean;
  `0002` applied, reversed to `0001` and re-applied on the dev database; G7 and G9 pass.
  CI run `45349326406` on branch `task/T-007-progress-models` is green.
- **Approved by:** Project owner (2026-11-23): «كمل».
- **References:** T-007, REQ-03, REQ-09, `docs/domain-model.md` §2.6–§2.9, `academy/models/progress.py`.

### [2026-11-24] — T-008: quiz and operational schema

- **Type:** Feature
- **Status:** Implemented
- **Summary:** `academy/models/quiz.py` adds the Phase 1 schema-only quiz tables: `Quiz`
  (version, optional lesson, pass mark, attempt cap), ordered `QuizQuestion` and `QuizChoice`,
  numbered `QuizAttempt` per enrollment and `QuizAttemptAnswer`. No endpoint reads or writes
  them; they exist so Phase 2 adds behaviour without a destructive migration.
  `academy/models/operations.py` adds the idempotency layer: `ReminderLog` unique per
  `(enrollment, kind, recipient_ref)`, `NotificationLog` unique per
  `(organization_id, dedupe_key, channel)` with the pending/sent/failed/skipped states and the
  rule that a `sent` row carries its timestamp, and `AuditEvent` with one event id per
  organization plus the object and time indexes.
- **Impact:** The last Phase 1–2 tables exist, so REQ-03's schema is complete and T-021/T-022
  can implement reminders and notifications against their keys. The audit append-only trigger
  is deliberately not created here: T-012 owns the audit service and its enforcement.
- **Evidence:** `tests/test_operational_models.py` (23 tests) covers the quiz ranges and
  uniqueness rules, the reminder and notification idempotency keys, the sent-timestamp rule and
  the audit event id uniqueness across organizations, plus the meta-test that every registered
  `academy` model subclasses `TenantModel`. `pytest -q` → 219 passed; `ruff check`,
  `ruff format --check`, `mypy .` and `makemigrations --check --dry-run` clean; `0003` applied,
  reversed to `0002` and re-applied on the dev database; G7 and G9 pass.
  CI run `45352655085` on branch `task/T-008-operational-models` is green.
- **Approved by:** Project owner (2026-11-23): «كمل».
- **References:** T-008, REQ-03, `docs/domain-model.md` §2.10–§2.13, T-012 (audit trigger).

