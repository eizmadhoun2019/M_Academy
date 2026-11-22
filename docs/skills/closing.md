# Skill: Close a task / phase gate

**Purpose:** Completion claims backed by evidence only.
**When to Use:** End of every task; phase gates.

## Steps
1. Work merged to `main` via PR; every applicable CI gate green on the exact merge commit.
   Verify the run's branch and head SHA.
2. Each acceptance criterion in STATUS has cited evidence (file+line, named test, or
   command output). Row becomes `[x]` with merge commit + CI link.
3. Documents updated per the sync table; LOG entry appended with evidence.
4. Report per RULES final report: task ID/state, merge SHA, CI link, criteria evidence,
   documents updated, deviations, next task. Then stop for the owner.
5. Phase gates (GATE-1): verify every REQ in CHARTER, record a `[RELEASE]` LOG entry,
   update STATUS counters/phase, stop for owner approval.

## Validation
`git log origin/main..<task-branch>` empty; worktree clean; STATUS/LOG truthful.
