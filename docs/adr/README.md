# ADR index

Architecture decision records for Masheed_Academy. The summary list lives in
`ARCHITECTURE.md` §11, which is normative; this directory holds the expanded record for each
decision that needed one.

**Naming:** `ADR-NNN-<slug>.md`. Never renumber an accepted ADR; supersede it with a new one
and mark the old one `Superseded by ADR-MMM`.

**Template:**

```markdown
# ADR-NNN — Title

- **Status:** Proposed | Accepted | Superseded by ADR-MMM
- **Date:** YYYY-MM-DD
- **Deciders:** Project owner / technical authority

## Context
What forces are in play.

## Decision
What we will do.

## Consequences
What becomes easier, what becomes harder, what must be revisited.
```

| ADR | Title | Status |
|---|---|---|
| ADR-012 | Membership comes from Hub on demand; no local membership projection | Accepted (2026-11-22) |
| ADR-013 | Watched coverage stored as merged ranges on one progress row, no per-heartbeat rows | Accepted (2026-11-22) |
| ADR-014 | Dual-mode H1 access (Hub-signed or local sign-in), `grants_only` default, Academy-local suspension | Accepted (2026-11-23, owner) |

ADRs 001–011 are the architecture decisions summarized in `ARCHITECTURE.md` §11; their text
there is authoritative until an expanded record is needed.
