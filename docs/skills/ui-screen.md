# Skill — Implement or review a UI screen

**Purpose:** implement a screen group from the official design reference without inventing visual
rules, duplicating components or claiming a visual pass that was not measured.
**When to use:** any task or checkpoint that creates, changes or reviews a public, auth, shell,
administration, learning, report, settings, dialog or state screen.

## Read first (in this order)

1. `docs/ui/design-system.md` — identity, master shell, components, responsive and acceptance rules.
2. `docs/ui/design-tokens.json` — the only values for colour, type, spacing, radius and layout.
3. `docs/ui/wireframes.md` — the group's reference board, task and gate status.
4. `docs/ui/screen-specification.md` — screen content, states (§5), responsive table (§6), journeys.
5. `docs/access-control.md` and `docs/api.md` — the permissions and contracts the screen must obey.
6. `docs/ui/design-reference.md` — fingerprints, asset gaps and restore, if a reference is needed.

## Steps

1. **Confirm eligibility.** The task is approved, its dependencies are `[x]`, and the group row in
   `wireframes.md` records the owner's approval (or a written waiver). Receiving the package alone
   is not approval; stop and report if the gate is open.
2. **Confirm scope.** Screen IDs, fields, actions and states come from the repository documents, not
   from a board. If a board shows something outside the approved scope, do not build it; note the
   difference in the report.
3. **Use the shell.** Extend the one Master Base Layout and existing partials. No second shell, no
   role-specific copy, no photographic banner inside the application.
4. **Tokens only.** Add no ad-hoc colour, spacing, radius or type value. Reuse or extend a shared
   component instead of creating a page variant; a genuinely new component is recorded in the
   design system before use.
5. **Mobile first.** Build and check 390 px first, then 768, 1024, 1440 and 1920, starting the
   verification at 320. Each width must reflow, not shrink: tables become labelled cards or scroll
   only inside their own container, dialogs stay visible, actions stay reachable, 44 × 44 px touch
   targets, no unjustified page-level horizontal scroll.
6. **Both directions.** Arabic RTL and English LTR with CSS logical properties; mirror layout but
   not video controls or identifiers; `dir="auto"` for user text and isolated LTR for email, UUID
   and time.
7. **States and permissions.** Implement the §5 state contract; render navigation and actions from
   effective permissions and still verify server-side. Hiding an item is not authorization and no
   company chooser exists.
8. **Accessibility.** Labelled controls, visible focus, logical keyboard order, focus-trapped
   dialogs with Escape, landmarks and headings, status announcements, contrast checked on rendered
   colours, reduced motion and 200 % zoom.
9. **Evidence.** Capture deterministic screenshots at the six widths in both directions, run axe
   and the keyboard check, and compare against the approved **implemented** baseline (never against
   a generated board). Store evidence per repository policy; keep boards out of Git.

## Validation

- `python scripts/check_docs.py` passes; no unresolved links or retired identifiers.
- Four or six-width render output, axe result and keyboard notes are attached to the task evidence.
- `git status` shows no design binary, package or reference image staged.
- The screen group's gate row and `LOG.md` entry name the evidence; a desktop-only pass is recorded
  as a failure, not a pass.
