# ORIO Operations UI — design contract (v6 refresh, 2026-10-06)

Design read: dense operations console for a service manager, industrial
character, leaning toward the Hermes app's own design system (native SDK
components) plus theme vars. Dials: variance 4, motion 2, density 8.

## System

- Components: Hermes SDK only (Button, Dialog family, SearchField,
  SegmentedControl, EmptyState, ErrorState, GlyphSpinner, ScrollArea,
  Separator). No custom buttons, no custom modal, no custom inputs.
- Radius lock: 8px everywhere (cards, tiles, pills are 20px by role:
  pills are the one documented exception).
- One accent: var(--ui-accent), used only for critical/attention states
  and the primary Approve action. Everything else is neutral text/borders.
- Type: app default stack. Tabular/mono numerals for wells, pages, dates,
  counts. Status is always a text pill, never a bare colored dot.
- States: every view covers loading (spinner), error (message + Retry),
  empty (message + next step). No decorative motion; transitions none.

## Layout

- Top bar: title, demo badge, safety note, How this works, Refresh.
- Left nav with live count chips (Today, Action Queue, Exceptions, Rigs total
  read live from the backend, never hardcoded). Nav is a landmark with
  aria-current on the active view.
- Content max 1200px. Tables: real thead with sticky elevated band
  (solid var(--ui-bg-elevated) + 2px divider, visible in every theme), row
  hover, critical row marker, scope cols, aria-labels, result counts.
- Job detail is a Dialog (Esc/backdrop close, footer safety note) with
  section headings (Evidence, Proposed actions, Documents), inline error +
  Retry state, and MDD MISSING lines called out in accent.
- Reject / Mark Incorrect use an inline confirm row (note + Confirm/Cancel),
  never a native prompt(). Exception notes are per-card state.
- Evidence job picker is a horizontal scroll tab row (SegmentedControl
  overflows with 6 jobs); unknown default job ids fall back to the first job.
- Job dialog queries run unconditionally (inactive side reads tiny cached
  /health) so hook order never changes between job and rig-well opens.
- History is a milestone timeline; ORIO/landing milestones accented.
  Null-stage guards throughout.
- Narrow (<720px): nav becomes a horizontal scroll row above content, tiles
  2-up. Reduced-motion respected.
- Today snapshot rail (v4): content max 1560px; table column + 300px sticky
  rail. Priority donut (tap segment or legend to filter, tap again to
  clear), lifecycle bars (tap drops the stage into search), approvals
  counts, and a Month-1 pilot-link card (HP-707 / THRY-961612, Milestone 1
  SAR 3,000 + VAT). Pure SVG, no libraries, accent-opacity steps only.
  Rail stacks to cards under 1100px. Search covers rig, well, finding,
  stage, action.
- Every view interactive (v5): Action Queue (decision-state donut + decided
  toggle), Rigs (stage bars, full 292 index client-filtered), Lifecycle
  (state donut), Exceptions (open/resolved donut), Evidence (status chips
  per job), History (Key milestones segment), Expansion (company bars +
  search). Same rail, donut, bar, and tab language everywhere.
- Lifecycle alignment rule (v6): toolbars sit full-width above the grid on
  every page, so rail top always meets table top. Evidence and History get
  full rails (job summary + entry-state bars; stage bars). Evidence status
  filter is shared between rail bars and entry chips.
