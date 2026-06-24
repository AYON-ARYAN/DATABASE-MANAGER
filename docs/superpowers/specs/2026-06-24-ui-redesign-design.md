# Meridian Data — UI Redesign Spec ("Bolder & Vibrant")

Date: 2026-06-24 · Branch: `react_build`

## Problem
The top navbar packs 10 text nav items + logo + DB chip + role + username + logout into one
56px row. At laptop widths (≤~1400px) items wrap to two lines and the right cluster clips
off-screen. The DB selector is also duplicated (navbar chip + a page-level dropdown). Pages
look inconsistent (some have gradient hero headers, some have none) and the Query page feels
empty.

## Goals
1. Fix the navbar so it never overflows and stays discoverable.
2. Unify the app shell (consistent page headers, background, spacing).
3. A cohesive, vibrant visual pass across all pages.
4. Verify every feature still works (no regressions / new bugs).

## Decisions (from brainstorming)
- **Navbar:** grouped **dropdown menus** (not an icon rail) — clear labels + uncluttered bar.
- **Scope:** full per-page redesign (shell first, then pages).
- **Style:** bolder / more vibrant (lean into gradient, glow, motion — kept tasteful).

## Navbar design — grouped dropdowns
Top bar: `⚡ Meridian` · **Query** (link) · **Workspace ▾** · **Insights ▾** · **Data ▾** · **Admin** (link)
Right cluster: single **DB switcher** (dropdown over `connections`/`switchDb`) · role badge · username · logout.

Grouping:
| Top-level | Children |
|---|---|
| Query (link) | Query (`/`) |
| Workspace ▾ | Command Center, Join Center |
| Insights ▾ | Overview, Dashboards, Analysis, Insights |
| Data ▾ | Databases, Samples, Snapshots |
| Admin (link) | Admin |

- Parent highlights when a child route is active.
- Dropdowns: glass + blur + gradient hover + soft glow; open on hover/click; click-outside + Esc close; keyboard accessible.
- Mobile: existing drawer, restyled, groups as expandable sections.

## Design system (touches every page)
- `index.css`: add an **aurora/gradient ambient background**, dropdown fade/scale animation, refined glass + glow tokens. Keep existing `glass`, `gradient-text`, `glow-*`, `fadeUp`.
- New/updated components in `src/components/ui/`:
  - `Dropdown.jsx` (headless, click-outside + Esc) — used by navbar + DB switcher.
  - `PageHeader.jsx` (icon + title + subtitle + actions slot).
  - Refine `Button`, `Card`, `Badge`, `EmptyState` for the bolder look.
- `AppShell.jsx`: render the aurora background behind `<main>`.

## Page work
- **Tier 1 (full internal redesign):** Login, Query, Overview, Dashboards, Databases.
- **Tier 2 (shell + components + tidy):** Command Center, Join Center, Analysis, Insights,
  Samples, Snapshots, Admin, Command Guide, Review, Create Database, Dashboard View.
- Remove the duplicated page-level DB selector where the navbar switcher now covers it.

## Components / boundaries
- `Navbar` consumes `NAV_GROUPS` (new export in `constants.js`) + `useDb()` — no business logic.
- `Dropdown` is presentation-only (open/close + a11y); callers supply trigger + items.
- Pages keep their existing API hooks/data flow untouched — this is a presentation refactor.

## Verification (every feature)
Run dev (`flask --app app run --port 5001` + `npm run dev`), drive Chrome:
1. Login flow (admin1/admin123) — redirect works.
2. Visit **every** nav route — none blank, no console errors.
3. Run a NL query (e.g. "show tables") — results render.
4. Switch DB via the navbar switcher — active DB updates everywhere.
5. Check 1280px + mobile (≤768px) — navbar never overflows; drawer works.
Screenshot each major page; fix bugs found; re-verify.

## Out of scope
- No backend/API changes. No new heavyweight deps (build Dropdown by hand; CSS/Tailwind motion).
- Secret-scan before any push (recent Gemini-key incident).
