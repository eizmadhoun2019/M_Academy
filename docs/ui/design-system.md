# Masheed Academy — Design System and Master Shell

**Status:** Adopted 2026-11-25 (D-045). Canonical for visual identity, the internal shell,
design tokens, component behaviour and visual acceptance.
**Source of truth:** `Masheed-Academy-Official-UI-UX-v1.0` (owner-approved); `R05-master` is the
controlling internal reference. Provenance, fingerprints and archive: `design-reference.md`.
**Scope:** presentation only. Functionality, permissions, routes and data stay owned by
`CHARTER.md`, `docs/access-control.md`, `docs/api.md` and `screen-specification.md`; a feature that
appears in a reference image but is not in the approved scope is **not** approved.

**Precedence:** security and approved functional contracts > owner decisions > this document >
`screen-specification.md` > reference imagery. If a reference image and a contract disagree, the
contract wins and the conflict is reported to the owner.

## 1. Identity

| Role | Token | Value | Use |
|---|---|---|---|
| Charcoal / brand | `brand` | `#101820` | Sidebar, primary text, dark surfaces |
| Brand gold | `gold` | `#E8AA23` | Accents, primary buttons, active markers |
| Canvas | `canvas` | `#F5F7FA` | Page background |
| Surface | `surface` | `#FFFFFF` | Cards, header, forms |
| Muted text | `muted` | `#526174` | Secondary text, captions |
| Border | `border` | `#DCE2EA` | Card and table hairlines |
| Focus | `focus` | `#1D4ED8` | Visible keyboard focus |

- **Typography:** Rubik (Arabic + Latin), locally hosted. Body 14, small 12, page heading 24
  (mobile 20), metric 28, line-height 1.5. The approved Rubik binaries are **not yet supplied**;
  until they are, no screen may claim brand-font compliance and no other brand font is substituted
  as approved (asset gap in `design-reference.md`).
- **Logo and geometric element:** official Masheed logo and gold geometry from the approved
  package. They are **not yet supplied as standalone files**; development uses a text placeholder.
  Never crop a logo out of a mockup, redraw the mark or publish mockup portraits.
- **Gold contrast:** dark text on gold (`#101820`), never white text on gold. Gold is not used for
  small text on white.
- **Imagery:** public pages and auth screens keep the approved architectural photography. **No
  photographic banner inside the application**, including dashboards and administration.
- **Icons:** one family, consistent with the existing stack; no icon font or new icon library
  without approval. Semantic colour is always paired with text or an icon.

## 2. Master shell (every internal screen)

One base layout serves every authorized role. What changes is content, actions and the authorized
navigation items — never the identity or the structure. Separate role shells or page-specific
copies of the same component are prohibited.

- Charcoal (`#101820`) sidebar with restrained gold decoration at its foot.
- White, fixed header with the page title, language switch, notifications and user menu.
- Light canvas, white cards, quiet borders, considered gold accents.
- Short page titles, one `h1` per page, optional breadcrumb, one primary action.
- Sidebar on the inline-start edge: **right in RTL, left in LTR**.
- Navigation is rendered from effective permissions; hiding an item is never authorization.
- Public layout (`/`) and auth layout are separate from the internal shell (no sidebar); they share
  the identity, tokens and components.

| Width | Navigation | Header | Content padding | Grid |
|---|---|---|---|---|
| 320–767 px | Bottom navigation (64 px + safe area, max four authorized destinations + More) and a drawer for the rest | 56 px | 16 px | One column |
| 768–1199 px | Drawer, or a 72 px rail when space is constrained | 64 px | 20 px | Two columns where readable |
| ≥ 1200 px | Persistent 240 px sidebar | 64 px | 24 px | 12 columns, 16–24 px gap, content max 1600 px |

Two KPI columns on mobile only when labels fit. Large desktop adds whitespace, not new
functionality. No company switcher or company-selection screen exists for ordinary users.

## 3. Mobile first and responsive rules (permanent)

Design and implementation order is **Mobile → Tablet → Desktop → Large Desktop**; a desktop design
shrunk to mobile is prohibited.

| Reference | Use |
|---|---|
| Mobile 390 px | Design base |
| Tablet 768 px | Design step |
| Desktop 1440 px | Design step / reference shell |
| Large desktop | Content max-width, no stretched panels |

Verification widths — every screen, Arabic RTL and English LTR:
**320, 390, 768, 1024, 1440 and 1920 px** (plus landscape). These are test widths, not necessarily
all CSS breakpoints; breakpoints and component sizes come from `design-tokens.json`.

| Requirement | Acceptance |
|---|---|
| Reflow | Content is reorganized per width, not scaled; no core function is lost on mobile |
| Overflow | No unjustified page-level horizontal scrolling at any verification width |
| Tables | Rows become labelled cards or lists on narrow screens; a complex table may scroll inside its own labelled container |
| Forms | Single-column, reachable controls, inline validation, keyboard-safe on mobile |
| Dialogs | Never leave the viewport; full-screen or sheet on mobile; focus trapped and restored |
| Charts / player | Responsive; accessible summary or table; player first on mobile |
| Touch | 44 × 44 px minimum for primary interactive controls, adequate spacing, no hover-only action |
| Direction | RTL/LTR mirror layout with CSS logical properties; not video controls or identifiers; `dir="auto"` for user text and isolated LTR for email, UUID and time |
| Overlap | No clipped, overlapping or hidden text and buttons |
| Accessibility | Keyboard-reachable, visible focus, labelled controls, screen-reader landmarks |

A screen that works on desktop and fails on mobile or tablet is **not complete**.

## 4. Components

Build once, reuse everywhere, style only from tokens.

| Component | Required behaviour |
|---|---|
| App shell / sidebar / header / mobile navigation | Section 2; permission-gated items; focus-managed drawer that closes on navigation |
| Page header | One `h1` (24 desktop / 20 mobile), short description, gold accent, primary action opposite the title; action stacks below on narrow screens |
| Buttons | Primary gold-on-dark or dark, secondary white with border, danger red; 44 px minimum; visible disabled reason; pending state prevents duplicate writes |
| Form controls | Label above, required marker with explanation, 44 px minimum, inline error, preserved non-sensitive input on failure |
| Cards / KPI | Radius 12, padding 16–24, quiet border; label, real value, optional verified trend; omit unavailable data |
| Data tables | 56 px minimum rows, sortable headers only where supported, actions menu; mobile cards keep every essential field and action |
| Filters / pagination | Labelled controls, reset, applied filters preserved; server metadata for pagination |
| Badges / status | Text + semantic colour, never colour alone |
| Tabs | Keyboard accessible, active gold underline |
| Progress | Actual server value, label and accessible value; no fabricated percentage |
| Dialogs | Focus trap/restore, Escape where safe, explicit cancel, destructive confirmation naming object and effect |
| Notifications / toasts | Non-blocking success toast only after the server confirms; persistent inline errors |
| Loading / empty / error states | Skeleton (neutral, reduced motion), empty explanation with an authorized next action, error with safe retry |
| Media | Responsive aspect ratio, native accessible controls or the approved player, captions when available |

Central tokens only; no ad-hoc visual values scattered through templates, and no per-page variant
of a shared component.

## 5. Tokens and styling rules

- `design-tokens.json` is the canonical token data (colour, type, spacing, radius, layout,
  breakpoints, component minima). `tokens.css` is its identical CSS projection and is available in
  the archive; T-029 integrates the values into the existing stylesheet architecture.
- The interim palette and font shipped by T-013 (`#F8FAFC` canvas, Noto Sans Arabic) are
  **superseded**; they remain in code until T-029 migrates the UI and are not a design reference.
- Strict CSP without `unsafe-inline`: no inline `style=` or `<script>`; styles and scripts ship as
  cacheable files.
- No new UI, CSS or JavaScript library and no build step without owner approval. Server-rendered
  templates and vanilla ES modules remain the stack.
- Every user-visible string comes from gettext (`ar` default RTL, `en` secondary).

## 6. Interaction states and accessibility

The screen state contract is `screen-specification.md` §5 (loading, empty, filtered empty, success,
validation error, unauthorized, forbidden, not found, rate limited, server error, timeout, offline,
disabled, confirmation, unknown outcome). Universal rules:

- Never show success before the server response; disable submit in flight; repeated submits are
  idempotent server-side.
- Errors never include stack traces, SQL, tokens, emails or another company's data.
- Destructive actions require confirmation and, for admin actions, a reason.
- WCAG 2.2 AA: labelled controls, visible focus, logical keyboard order, 44 px targets, no
  colour-only meaning, 200 % zoom and reflow, reduced motion respected, accessible dialogs.
- Verify contrast on rendered colours and states; no compliance claim without test output.

## 7. Visual acceptance (V01–V11)

| ID | Test | Evidence |
|---|---|---|
| V01 | Same shell across all authorized roles; no internal image banner | screenshots + DOM assertions |
| V02 | 320×568, 390×844, 768×1024, 1024×768, 1440×900, 1920×1080; no page overflow | Playwright viewport matrix |
| V03 | Arabic RTL and English LTR; logical alignment and wrapping | screenshots both directions |
| V04 | Keyboard, focus, dialogs, labels, contrast, 44 px targets, zoom/reflow | axe + manual keyboard/zoom |
| V05 | Loading, empty, filtered empty, error, forbidden, expired session, pending, success | fixture-based tests |
| V06 | Unauthorized actions hidden **and** direct API/URL denied; cross-tenant attempts denied | integration tests |
| V07 | Assignment preview, deduplication, due date, auto-enrolment, scoped targets | service/API/E2E regression |
| V08 | Server-authoritative progress, locked lessons, media failure, completion | service/API/E2E regression |
| V09 | Official assets only; no sample data, unsupported features or company switch | owner visual review |
| V10 | Deterministic screenshot comparison against the approved implemented baseline | diff artifacts + reviewer |
| V11 | Capability matrix and applicable G1–G12 gates | traceability + CI links |

**Screenshot protocol:** fixed browser/version, viewport, locale, timezone, deterministic synthetic
fixtures, loaded fonts, reduced motion, stable clock; mask only genuinely nondeterministic data and
document every mask. Compare the same viewport, locale and state. Initial diff threshold 0.5 %
changed pixels, subject to owner calibration; any shell/brand/layout regression fails regardless of
the threshold. **No baseline auto-update** to hide failures. Baselines come from approved
implemented screens — **never from generated PNG boards**, which are visual intent, not pixel
specifications.

## 8. Verification workflow (per screen group)

1. Reconcile the group's screen IDs with the current plan task and the real routes/permissions.
2. Record the group's reference in `wireframes.md`; obtain the owner's group approval or a written
   waiver. Receiving the package does not close a group gate.
3. Design and build Mobile first, then Tablet, Desktop and Large Desktop.
4. Run the state contract, axe, keyboard, touch-target and RTL/LTR checks.
5. Capture the six verification widths plus landscape, and run visual regression against the
   approved implemented baseline.
6. Record evidence in the task card and `LOG.md`. Similarity to a mockup is never a visual pass.
