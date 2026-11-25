# Skill: Close a task or phase gate

**Purpose:** Completion claims backed by evidence only, under the «كمل» protocol.
**When to Use:** End of every task/checkpoint; phase gates.

## Steps
1. Re-read `docs/plan.md` for this task's acceptance criteria and `RULES.md` for the applicable
   gates. A criterion that is not listed is not added silently; it is a scope change.
2. Run the task's tests and gates locally; record exact commands and results. Do not pipe a
   command through `tail` without preserving its exit status. A skipped/inactive gate is reported
   as inactive with its reason, never as green.
3. Update `docs/plan.md` only if a checkpoint/criterion changed with owner approval. Update the
   owning documents from the RULES sync table (domain, API, access-control, security,
   notifications, reports, jobs, UI, configuration, operations, migration as applicable).
4. Fill `STATUS.md`: state `[x]` only with the commit, CI run and named evidence; `[~]` for
   partial work with the remaining checkpoint; `[!]` with the blocker and the decision needed.
5. Append `LOG.md` with date, task, summary, evidence links and deviations. Never rewrite history.
6. Commit with a Conventional Commit ≤72 characters and `Refs: T-NNN`; push the task branch. Do
   **not** merge to `main` without the owner's approval.
7. Report per RULES §final report: task/state, commit/branch, gates and tests actually run,
   documents updated, deviations, risks, next task. Then stop.

## Validation
`git status` clean; branch pushed; `python scripts/check_docs.py` green; every `[x]` has a
clickable/named evidence item; `STATUS`/`plan`/`traceability` agree on the task state. For
GATE-1: every REQ-01…REQ-28 verified, a `[RELEASE]` LOG entry exists, and the owner has approved.
