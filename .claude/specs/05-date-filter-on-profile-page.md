# Spec: Date Filter on Profile Page

## Overview

The profile page built in step 04 and enriched in step 05 (well, this spec) shows summary tiles, a category bar chart, and the 5 most recent transactions. As a user accumulates expenses, those three sections lose signal: the "Total spent" tile becomes a number the user can't contextualise, and "Recent transactions" mixes today's chai with last month's rent. This step adds a **date-range filter** to `/profile` so the user can scope the summary tiles, the category bar chart, and the recent-transactions list to a chosen window. Two preset chips (`This month`, `All time`) plus two manual `from`/`to` date inputs give users an obvious default and an escape hatch. The filter is GET-driven (URL query string) so the filtered view is shareable and survives reload. Adding expenses, editing, and deleting stay out of scope — the page remains read-only.

## Depends on

- Step 01 — Database setup (`expenses.date` column stores `YYYY-MM-DD` strings; `get_db()` helper).
- Step 02 — Registration (`session["user_id"]`).
- Step 03 — Login and Logout (`_current_user()`, PRG flash pattern, auth-aware navbar).
- Step 04 — Profile Page Design (`/profile` route, `templates/profile.html`, the `/* Profile */` CSS block).
- Step 05 (previous: profile-info) — summary tiles (count, total, top category), category bar chart, recent 5 transactions list. **This step is layered on top of that work and must not regress any of it.** The data currently computed in `profile()` (count, sum, top category, recent 5, category totals) becomes the data computed **for a filtered subset**.

## Routes

No new routes. The existing `GET /profile` handler in `app.py` is extended to accept query-string parameters and to compute the same aggregates against the filtered subset.

- `GET /profile?from=YYYY-MM-DD&to=YYYY-MM-DD` — Authentication check unchanged from step 04. When logged in, additionally:
  1. Read `from` and `to` from `request.args`. Both are optional. Defaults: `from` omitted → "all time" lower bound (`0000-01-01`); `to` omitted → "all time" upper bound (`9999-12-31`). This keeps the unfiltered case behaviourally indistinguishable from today.
  2. Validate the dates. Each must parse as `YYYY-MM-DD` via `datetime.strptime(..., "%Y-%m-%d")`. If parsing fails on either, flash a single user-facing error ("Please enter valid dates (YYYY-MM-DD).") and redirect to `/profile` (unfiltered). A range where `from > to` is treated the same way: flash and redirect. Do **not** crash, do not render with a silently empty result.
  3. Pass the validated `from` and `to` strings (plus Python `date` objects for default-value detection) into every aggregate query so count, sum, top category, recent 5, and category totals all reflect the same subset.
  4. Echo the filter state to the template so the chips can highlight the active preset (or neither, when a manual range is in effect), the date inputs can show the current values, and an "Active: …" caption can appear above the data.

  Access level: **logged-in**. The not-logged-in (`_current_user() is None`) and stale-session (`user_row is None`) branches stay exactly as step 04 wrote them. Filter validation runs **after** the auth check, only inside the authenticated branch.

## Database changes

No database changes. The `expenses` table already has the `date TEXT NOT NULL` column (`database/db.py:60`). Filtering is a `WHERE date BETWEEN ? AND ?` clause on that existing column.

## Templates

- **Modify:** `templates/profile.html` — Keep every section that step 04 and step 05 (profile-info) built: identity header, summary tiles, category bar chart, recent transactions, sign-out button. **Above** the existing `.profile-stats` block, add a `.profile-filter` card containing:
  1. **Preset chips** — two buttons, `This month` and `All time`. `All time` is a link to `/profile` (no query string). `This month` is a link to `/profile?from=YYYY-MM-01&to=YYYY-MM-DD` where both endpoints are computed in Python from `date.today()` and passed to the template. The chip matching the current active range gets an `is-active` class (CSS handles the visual). When the user has picked a custom range with neither preset matching, both chips render in their inactive state.
  2. **Manual range form** — a small `<form method="get" action="/profile">` with two `<input type="date" name="from">` and `<input type="date" name="to">` plus an "Apply" submit button. Values are pre-filled from the current `from` / `to` query params (empty when "All time" is active). Submitting POSTs nothing — this is GET, so the URL updates with the new query string and the page re-renders.
  3. **Active-range caption** — a single muted line below the filter card: `Active: <from> → <to>` when a filter is in effect, hidden (or absent from the DOM) when "All time" is active. Use the existing `profile-meta` / `profile-empty` style classes; do not invent new typography.

  The summary tiles, category bar chart, and recent transactions sections render **exactly as today** — only the data they iterate over changes. No template logic moves from Python into Jinja. The existing empty states (`No expenses yet`, `No transactions yet`) stay and now apply to the filtered subset (e.g. a user with expenses only in July filtering to August sees both empty states; that's correct).

- **Modify:** `static/css/style.css` — Append a `/* Profile Filter */` block at the bottom (after `/* Profile Info */`). Style the filter card, the preset chips (including the `is-active` state), the date inputs, and the active-range caption. Reuse existing CSS variables (`--surface`, `--border-soft`, `--accent`, `--ink`, `--ink-soft`, `--ink-muted`). No hex literals.

## Files to change

- `app.py` — Extend the `profile()` view:
  1. Parse `from` and `to` from `request.args` after `user_row is None` check.
  2. Validate each via `datetime.strptime(..., "%Y-%m-%d")`. On any `ValueError`, flash + redirect to `/profile` (unfiltered).
  3. If `from > to`, flash + redirect to `/profile`.
  4. Add a `BETWEEN ? AND ?` clause (with the defaulted `from` / `to` bound values) to **every** aggregate SELECT currently in `profile()`: count+sum, top category, recent 5, category totals. Use a single bound pair; do not duplicate the literal dates across queries.
  5. Compute the preset URLs (`all_time_url`, `this_month_url`) and pass them to the template, plus the active-range caption text (or a sentinel the template can branch on).
  6. Pass `filter_from` / `filter_to` (the strings the user is currently seeing) and the parsed `date` objects for chip-highlight logic.

  Imports gain `from datetime import date, datetime`.

- `templates/profile.html` — Add the `.profile-filter` block above `.profile-stats`. Pre-fill the date inputs from the current `from` / `to`. Highlight the active chip via an `is-active` class. Render the active-range caption. No other section changes.

- `static/css/style.css` — Append `/* Profile Filter */` block. New classes: `.profile-filter`, `.profile-filter-presets`, `.profile-chip`, `.profile-chip.is-active`, `.profile-filter-form`, `.profile-filter-range`, `.profile-filter-active`. Reuse existing variables.

## Files to create

None. All changes are edits to existing files.

## New dependencies

No new dependencies. `datetime` is in the Python standard library (already imported indirectly via nothing — adding it to the imports list at the top of `app.py` is sufficient). No new pip packages, no new JS, no new frontend assets.

## Rules for implementation

- No SQLAlchemy or ORMs. Use `sqlite3` directly via `database.db.get_db()`.
- Parameterised queries only — every `BETWEEN ? AND ?` clause must use `?` placeholders. No f-strings inside SQL. The single bound pair is computed once and reused across all five SELECTs (count+sum, top category, recent 5, category totals) so the filter logic stays in one place.
- The `profile()` view remains **GET-only**. Do not add `methods=["POST"]`. The manual range form submits via GET.
- Re-use the existing `_current_user()` helper from step 03. Do not introduce a second source of truth for login state.
- Keep the existing not-logged-in and stale-session branches exactly as step 04 wrote them. Filter parsing happens **after** the auth check.
- Default bounds are `0000-01-01` (lower) and `9999-12-31` (upper). Both pass `datetime.strptime(..., "%Y-%m-%d")` validation cleanly. The SQLite `BETWEEN` operator is inclusive on both ends (`x BETWEEN a AND b` is true), so the defaults reproduce the unfiltered behaviour exactly. Do **not** use `NULL` as the default — `BETWEEN date AND NULL` always evaluates to false in SQLite and would silently zero out the aggregates.
- Validation order in `profile()`:
  1. `_current_user()` check → redirect to `/login` if missing.
  2. Fetch `user_row` → clear session and redirect to `/login` if missing.
  3. Read + validate `from` and `to` query params → flash + redirect to `/profile` (unfiltered) on any error.
  4. Run the five filtered SELECTs.
  5. Render the template.
- `BETWEEN` is inclusive on both ends. A user filtering to "August 2026" expects `from=2026-08-01&to=2026-08-31` to include expenses on both those dates. Document this in a code comment above the query so the intent is obvious.
- The `This month` preset URL is computed in Python from `date.today()` and passed to the template as a string. The template does not compute dates; it only echoes the strings the view gives it.
- Date inputs use `<input type="date">` so the browser-native picker works. The `name` attributes are `from` and `to` (matches the query-string keys). When the form is submitted with both fields empty, the URL becomes `/profile?from=&to=` — the validation step treats empty strings as "use default" rather than as an error.
- The "Active" caption is rendered only when `filter_from != "0000-01-01"` or `filter_to != "9999-12-31"`. The template can branch on this with a simple Jinja `{% if %}` — no extra Python plumbing required.
- All templates extend `base.html`. Per-page JS (if any) goes in `{% block scripts %}`. This step does **not** add new JS — the chips are plain `<a>` tags and the form submits naturally. If a future revision wants to make the chips submit the form via JS, that's a separate step.
- `app.py` must continue to call `init_db()` and `seed_db()` on startup as it does today — do not regress the bootstrap.
- Keep `debug=True`, `port=5001`. Do not change the dev server port.
- All amounts formatted as INR with the `&#8377;` rupee symbol (no `&rupee;`, no literal `₹`). Dates formatted as `YYYY-MM-DD`. Reuse the formatting helpers the step 05 (profile-info) work introduced.

## Definition of done

- [ ] Visiting `/profile` while logged in as the demo user with **no query string** shows the page **exactly** as it did before this step: `Total expenses 8`, `Total spent ₹9,448.00`, `Top category Shopping`, 7 category bars, 5 recent transactions. The "All time" chip has the `is-active` class; the "This month" chip does not. No active-range caption is rendered.
- [ ] Visiting `/profile?from=2026-08-01&to=2026-08-31` while logged in as the demo user shows: `Total expenses 8`, `Total spent ₹9,448.00` (every seeded expense falls in August), `Top category Shopping`, all 7 category bars present, all 5 recent transactions visible. The "This month" chip has `is-active`. The active-range caption reads `Active: 2026-08-01 → 2026-08-31`. The two date inputs are pre-filled.
- [ ] Visiting `/profile?from=2026-08-05&to=2026-08-07` while logged in as the demo user shows: `Total expenses 3` (`Bills 1850` on the 4th is excluded, `Other 320` on the 7th is included; wait — `Other 320` is on `2026-08-07` per the seed), recompute against the seed: rows dated `2026-08-05` (Entertainment 599), `2026-08-06` (Health 450), `2026-08-07` (Other 320) → `Total expenses 3`, `Total spent ₹1,369.00`, `Top category Entertainment ₹599.00`, 3 category bars, 3 recent transactions in the list. **Verify against the actual seed before claiming this passes.**
- [ ] Visiting `/profile?from=2026-12-01&to=2026-12-31` while logged in as the demo user shows: `Total expenses 0`, `Total spent ₹0.00`, `Top category —`, the category bar chart card shows `No expenses yet`, the recent transactions card shows `No transactions yet`. No 500, no `None` literal in the rendered HTML. The active-range caption is rendered.
- [ ] Visiting `/profile?from=garbage&to=2026-08-31` while logged in as the demo user redirects (302) to `/profile` (no query string) with the validation flash `Please enter valid dates (YYYY-MM-DD).`. The unfiltered page renders normally.
- [ ] Visiting `/profile?from=2026-08-31&to=2026-08-01` while logged in as the demo user redirects (302) to `/profile` (no query string) with the same flash message. (Reversed range.)
- [ ] Visiting `/profile?from=&to=` while logged in as the demo user behaves like `/profile` (empty inputs are treated as defaults, not errors).
- [ ] Visiting `/profile` while NOT logged in redirects (302) to `/login` with the step 04 flash `Please sign in to view your profile.`. The new code does not change this behavior.
- [ ] Clicking the "All time" chip on a filtered view navigates to `/profile` (no query string) and renders the unfiltered page.
- [ ] Clicking the "This month" chip on any view navigates to `/profile?from=<YYYY>-<MM>-01&to=<YYYY>-<MM>-<DD>` for today's date and renders the filtered page with that range active.
- [ ] Submitting the manual range form with `from=2026-08-01&to=2026-08-15` navigates to `/profile?from=2026-08-01&to=2026-08-15` and renders the filtered page (verified against the seed).
- [ ] `password_hash` is never SELECTed in the new queries and never reaches the template. Grepping the rendered HTML for `pbkdf2`, `scrypt`, `password`, `werkzeug`, or `password_hash` returns nothing.
- [ ] All modified SELECT queries use `?` placeholders. Grepping `app.py` for SQL f-strings or `%` formatting inside SQL returns nothing new.
- [ ] All new CSS uses existing CSS variables. The `/* Profile Filter */` block contains zero hex literals — `grep -n "#[0-9a-fA-F]\{3,6\}" static/css/style.css` shows the same set of hex literals as before this step.
- [ ] The rupee symbol appears as `&#8377;` in the template source, never as a literal `₹` character.
- [ ] `app.run(debug=True, port=5001)` starts cleanly. No new tracebacks on any of the paths above.
- [ ] No new pip packages installed (`pip freeze` is unchanged from before this step). The `datetime` import is from the standard library.
- [ ] Every page that worked before this step (`/`, `/login`, `/register`, `/logout`, `/terms`, `/privacy`, `/profile` unfiltered) continues to behave identically when this step is layered on top.