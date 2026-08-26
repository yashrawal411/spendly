# Spec: Add Expense Management

## Overview

The profile page built up through steps 04 and 05 shows the user a read-only dashboard — summary tiles, a category bar chart, the 5 most recent transactions, and a date-range filter. The user can see their data, but they cannot act on it from inside Spendly: adding, editing, and deleting expenses are still placeholder strings in `app.py` (`/expenses/add`, `/expenses/<int:id>/edit`, `/expenses/<int:id>/delete`), and there is no UI surface for any of them. This step moves the full expense management flow onto a **dedicated page** at `/expenses`. The page combines four things in one place: an inline "Add expense" form, a date-range filter (the same `from` / `to` chips-and-form that `/profile` already has), a "Top category" tile so the user can confirm where their money is going, and a paginated list of expenses with per-row edit and delete actions. The `/profile` page is slimmed down at the same time — the add-expense form and the date filter are removed from it, since both now live (and are richer) on `/expenses`. The category bar chart and the recent-transactions list stay on `/profile` because they are summary widgets, not management actions. The result is a clear separation of concerns: `/profile` answers "how am I doing?", `/expenses` answers "what do I want to do with my records?".

## Depends on

- Step 01 — Database setup (`expenses` table with `id`, `user_id`, `amount`, `category`, `date`, `description`; `get_db()` helper; FK `ON DELETE CASCADE`).
- Step 02 — Registration (`session["user_id"]`, `session["user_name"]`).
- Step 03 — Login and Logout (`_current_user()`, PRG `flash()` + `redirect()` pattern, `/logout` route, auth-aware navbar).
- Step 04 — Profile Page Design (`/profile` route, `templates/profile.html`, summary tiles, category bar chart, recent-transactions list).
- Step 05 — Date Filter on Profile Page (the `from` / `to` query-string filter with `BETWEEN ? AND ?` semantics; the `All time` / `This month` preset chips; the validation rules). **The same filter is reused on `/expenses` — do not reinvent it.**
- Step 06 — Add Expense on Profile Page (per the current `master` HEAD: the `add_expense` route at `/expenses/add` exists as a placeholder. This step replaces the placeholder with a real POST handler and lifts the form onto the new `/expenses` page.) **Treat the current `feature/add-expense-on-profile-page` branch as already-merged into this step's mental model: the placeholder `add_expense` route is deleted and a real handler takes its place.**

## Routes

Four routes. Three are new, one is a placeholder that gets replaced.

- `GET /expenses` — New. Logged-in only. Renders `templates/expenses.html` with: the user's name, the current `from` / `to` filter state (same query-string keys as `/profile`), the preset URLs (`All time`, `This month`), the **top category** for the filtered subset (category name + total amount; `None` when zero expenses match), and the **full list** of expenses for the filtered subset (no `LIMIT 5` — every row). The list is ordered `date DESC, id DESC` so the most recent expense is on top. The form on the page is pre-populated from `flashed` form data on a failed POST (see `POST /expenses/add`).
- `POST /expenses/add` — New. Logged-in only. Validates form input (`amount`, `category`, `date`, optional `description`), inserts a new `expenses` row scoped to `_current_user()`, then `flash("Expense added.")` and `redirect(url_for("expenses"))` (PRG). On validation failure, `flash(error)` and `redirect(url_for("expenses"))` with the form values re-populated in the template from `session` (see "Form re-population" below).
- `POST /expenses/<int:id>/edit` — New. Logged-in only. Replaces the existing placeholder route of the same path. Loads the expense by `id AND user_id = _current_user()` (so a user cannot edit another user's row — 404, not 403, to avoid leaking IDs). Validates the same fields as add. Updates the row in place. Flashes `"Expense updated."` and redirects to `/expenses` (preserving the current `from` / `to` query string).
- `POST /expenses/<int:id>/delete` — New. Logged-in only. Replaces the existing placeholder route of the same path. Loads the expense by `id AND user_id = _current_user()` (404 otherwise). Deletes the row. Flashes `"Expense deleted."` and redirects to `/expenses` (preserving `from` / `to`).

The three placeholder strings in `app.py` (`/expenses/add`, `/expenses/<int:id>/edit`, `/expenses/<int:id>/delete`) — all of which today return hardcoded `"coming in Step N"` strings — are replaced with the real handlers above. The URL paths do not change.

Access level: **all four routes are logged-in.** The not-logged-in branch (`_current_user() is None`) flashes `"Please sign in to manage your expenses."` and redirects to `/login` exactly as `/profile` does today. The stale-session branch (`user_row is None`) clears the session and redirects to `/login` exactly as `/profile` does today.

## Database changes

No database changes. The `expenses` table from step 01 (`database/db.py:55`) already has every column this step needs (`id`, `user_id`, `amount`, `category`, `date YYYY-MM-DD`, `description`, `created_at`). All writes are `INSERT` and `UPDATE` and `DELETE` against that existing schema. No new tables, no new columns, no new indexes, no schema migrations.

The data ownership invariant is enforced at the query level: every SELECT, UPDATE, and DELETE against `expenses` includes `AND user_id = ?` so users can only see and modify their own rows. There is no admin role and no cross-user access.

## Templates

- **Create:** `templates/expenses.html` — New page. Extends `base.html`. Layout (top to bottom):
  1. **Page header** — `Expenses` title, sub-line `"Manage every rupee you spend."` Reuse the typography from `profile.html` (`Hi, {{ name }}` style header / `profile-subtitle` / `profile-meta` classes are fine; do not invent new typography).
  2. **Top-category tile** — single card showing `Top category: <name>` and `&#8377;<amount> spent` below. When `top_category` is `None`, render `—` and `&#8377;0.00 spent` (matches the `/profile` empty-state contract from step 04).
  3. **Date filter** — same `.profile-filter` block that step 05 introduced: `All time` chip, `This month` chip, `from` / `to` date inputs with an Apply button, active-range caption. **Lift the markup verbatim from `profile.html`** so the two pages look identical for the filter. (Do not extract a Jinja partial — `profile.html` keeps its own copy; the duplication is intentional and called out in the Rules.)
  4. **Add expense form** — a `<form method="post" action="{{ url_for('add_expense') }}">` with four fields: `amount` (number, step="0.01", min="0.01", required), `category` (`<select>` with the seven categories from step 01: `Food`, `Transport`, `Shopping`, `Bills`, `Entertainment`, `Health`, `Other`; required), `date` (`<input type="date" name="date">`, default to today, required), `description` (`<input type="text" name="description" maxlength="200">`, optional). Submit button says `Add expense`. On validation failure, pre-fill the four fields from the `form_data` dict the view passes in (see Rules).
  5. **Expense list** — a `<table>` with columns: `Date`, `Category`, `Description`, `Amount`, `Actions`. One row per expense in the filtered subset. The `Actions` cell holds two small `<form>` elements: an "Edit" button that swaps the row into an inline edit form (see Edit affordance below), and a "Delete" button. **Delete must be a `POST` form, never an `a` tag**, so CSRF and confirm-via-JS are the only paths. A tiny inline `onsubmit="return confirm('Delete this expense?');"` on the delete form is acceptable vanilla JS; it does not require a build step.
  6. **Empty state** — when the filtered subset is zero rows, show `No expenses yet. Use the form above to add one.` instead of the table (matches the `profile-empty` style from step 04).

  **Edit affordance:** the cleanest approach that does not require a separate `/expenses/<id>/edit` GET page is to render the edit form **inline** in the same row: clicking "Edit" hides the row's data cells and shows the four input fields pre-filled with the row's current values, plus a `Save` button (`POST /expenses/<id>/edit`) and a `Cancel` button (just a link that reloads the page without `?edit=`). This is implemented with a `?edit=<id>` query string on `/expenses`: when the query string has `?edit=<id>` and the row exists and belongs to the current user, the matching row renders its edit form; all other rows render the read-only data. The `<a class="expenses-row-edit" href="?edit={{ row.id }}">Edit</a>` link is the trigger. `Cancel` is `<a href="{{ url_for('expenses') }}">Cancel</a>` (no `?edit=`). The implementation does **not** need new JavaScript; query-string-driven rendering is sufficient. (Vanilla JS to toggle visibility is acceptable as an alternative but is not required.)

- **Modify:** `templates/profile.html` — **Remove** the following blocks:
  1. The entire `.profile-filter` block (the date filter and the active-range caption) — this is the entire `<div class="profile-filter">…</div>` element on `profile.html:19–46`. It now lives only on `/expenses`.
  2. The `Top category` tile in `.profile-stats` stays (it's a summary widget), but the user can no longer filter it on this page, so the tile reflects the **all-time** totals again — same as step 04 before the date filter was layered in. The "Total spent" and "Total expenses" tiles also reflect all-time totals on `/profile` from this step forward.
  3. **Keep** the recent-transactions list and the category bar chart on `/profile`. They are summary widgets and remain useful on the dashboard. They are now computed against the all-time subset (no `BETWEEN` filter), because the filter is gone from this page.
  4. **Keep** the identity header, the "Sign out" button, and the empty states. Title stays `Your profile — Spendly`.

  In practice, the simplest implementation is to **delete** the filter block from `profile.html` and **stop** passing `filter_from`, `filter_to`, `this_month_url`, `all_time_url`, `is_all_time`, `is_this_month` to the `profile.html` render. The `profile()` view in `app.py` is simplified to its step 04 shape (no query-string parsing, no `BETWEEN` filter on the queries), and the template no longer references those variables.

- **Modify:** `static/css/style.css` — Append a new `/* Expenses */` block at the bottom (after `/* Profile Filter */`). New classes only: `.expenses-page`, `.expenses-top-category`, `.expenses-add-form`, `.expenses-form-row`, `.expenses-form-field`, `.expenses-form-actions`, `.expenses-list`, `.expenses-list-table`, `.expenses-row-amount`, `.expenses-row-actions`, `.expenses-row-edit-form`, `.expenses-cancel-link`. Reuse existing variables (`--surface`, `--border-soft`, `--accent`, `--ink`, `--ink-soft`, `--ink-muted`, `--danger` for the delete button). Zero hex literals in the new block.

- **Modify:** `templates/base.html` — **Add** a link in the navbar for signed-in users pointing at `/expenses`. Place it between the greeting and the Sign-out link: `<a href="{{ url_for('expenses') }}">Expenses</a>`. The signed-out branch (Sign in / Get started) is unchanged. No link on this page for signed-out users because `/expenses` requires auth.

## Files to change

- `app.py` — Substantial changes:
  1. **Replace** the three placeholder routes (`/expenses/add`, `/expenses/<int:id>/edit`, `/expenses/<int:id>/delete`) with real handlers per the Routes section.
  2. **Add** the `GET /expenses` handler. It mirrors the filter-parsing logic from step 05's `profile()` (date validation, defaulted bounds, `from > to` rejection) but with two differences: it queries **all** matching expenses (no `LIMIT 5`), and it always computes the top-category aggregate against the filtered subset.
  3. **Extract** a small private helper `_validate_expense_form(amount, category, date, description)` that returns `None` on success or a user-facing error string. Used by both add and edit. Categories are a fixed tuple: `("Food", "Transport", "Shopping", "Bills", "Entertainment", "Health", "Other")` — these are the seven categories the seed inserts, and the `<select>` in the template offers exactly these.
  4. **Simplify** the `profile()` view back to its step 04 shape: identity header, three summary tiles (count, total, top category — all-time), category bar chart (all-time), recent 5 transactions (all-time). The step 05 filter code (`DEFAULT_FROM`, `DEFAULT_TO`, the `strptime` validation block, the `BETWEEN` clauses, the `flash` redirects) is **deleted** from `profile()`. The template receives only the step 04 payload.
  5. Imports gain nothing new — `re`, `sqlite3`, `datetime.date`, `datetime.datetime`, `flask.{...}`, `werkzeug.security` are already imported. `datetime` is already used by the current `profile()`.
  6. Define a module-level constant `EXPENSE_CATEGORIES = ("Food", "Transport", "Shopping", "Bills", "Entertainment", "Health", "Other")` so the template's `<select>` and the validator share one source of truth (passed to the template as a Jinja variable).

- `templates/profile.html` — **Delete** the entire `.profile-filter` block (lines 19–46 in the current file). Stop referencing `filter_from`, `filter_to`, `this_month_url`, `all_time_url`, `is_all_time`, `is_this_month` in the template. The summary tiles, bar chart, and recent transactions stay; they are computed against the all-time subset.

- `templates/base.html` — Add the `Expenses` link to the navbar's signed-in branch.

- `static/css/style.css` — Append `/* Expenses */` block. New classes, existing variables, zero hex literals.

## Files to create

- `templates/expenses.html` — The new management page. Extends `base.html`. Renders the top-category tile, the date filter (lifted from `profile.html`), the add form, and the expense list with edit / delete actions.

## New dependencies

No new dependencies. Everything is `sqlite3` (already used), `datetime` (already used), Jinja (already used), and vanilla JS only (the optional `confirm()` on delete and the optional inline-edit toggle). No new pip packages, no new JS libraries, no frontend build step.

## Rules for implementation

- No SQLAlchemy or ORMs. Use `sqlite3` directly via `database.db.get_db()`.
- Parameterised queries only — every `INSERT`, `UPDATE`, `DELETE`, and `SELECT` against `expenses` uses `?` placeholders. No f-strings, no `%` formatting inside SQL.
- **Ownership invariant** — every query that reads or writes a single expense by `id` MUST include `AND user_id = ?` (or `WHERE id = ? AND user_id = ?`). A row that doesn't match returns `None` and the handler responds with `abort(404)` (or `return "Not found", 404`). This is a security requirement, not a UX nicety: never trust the `id` from the URL.
- All four new `/expenses/*` routes require auth. The not-logged-in branch uses the same flash + redirect as `/profile` (a slightly different message is fine, e.g. `"Please sign in to manage your expenses."`).
- Use the existing `_current_user()` helper from step 03. Do not introduce a second source of truth for login state.
- The three POST routes (`/expenses/add`, `/expenses/<id>/edit`, `/expenses/<id>/delete`) all return `redirect(url_for("expenses"))` with the original `from` / `to` query string preserved. Use `request.args.to_dict()` or pass through the current `request.url` parameters explicitly. Editing and deleting should land the user back on the same filtered view they were on.
- The `add_expense` handler accepts `methods=["POST"]` only — no `GET`. A GET to `/expenses/add` redirects to `/expenses` so users can share the URL safely.
- The `edit_expense` and `delete_expense` handlers also accept `methods=["POST"]` only. They replace the current `GET`-only placeholders. **No GET handlers** — get-then-render happens on `/expenses?edit=<id>` instead.
- Validation helper `_validate_expense_form(amount_raw, category, date_raw, description)`:
  - `amount` must parse as a positive float. Use a try/except around `float(amount_raw)`; reject on `ValueError`, `None`, `<= 0`, or `> 1_00_00_000` (sanity cap, one crore). Format the error as `"Please enter a valid amount."`.
  - `category` must be in `EXPENSE_CATEGORIES` (case-sensitive). Reject with `"Please pick a category."` if not.
  - `date` must parse as `YYYY-MM-DD` via `datetime.strptime(..., "%Y-%m-%d")`. Reject with `"Please enter a valid date (YYYY-MM-DD)."` on `ValueError`.
  - `description` is optional; strip whitespace; truncate to 200 chars. Empty string becomes `None` on insert.
  - First failed check returns immediately. The helper returns `None` on success.
- **Form re-population** on validation failure: stash the user's input in `session["expense_form_draft"]` before the redirect (a small dict with `amount`, `category`, `date`, `description`), then `pop` it on the next GET of `/expenses` and pass it to the template as `form_data`. The template branches `{% if form_data %}` to pre-fill the four inputs. After a successful POST or after a successful GET-without-flash, the draft is cleared. This is the standard PRG pattern; do not render the form with stale values from a hidden input (the redirect-after-failure would lose them).
- Date filter on `/expenses` mirrors step 05 exactly: `from` and `to` query params, both optional, defaults `0000-01-01` / `9999-12-31`, `strptime` validation, `from > to` rejection, `BETWEEN` inclusive on both ends. The same flash + redirect pattern. The same preset chips. **Do not extract a shared `_parse_date_filter()` helper** in this step — the duplication between `profile()` (now slim) and `expenses()` is acceptable; refactor only if a third call site appears.
- All templates extend `base.html`. Per-page JS (if any) goes in `{% block scripts %}`. Inline event handlers (`onsubmit="return confirm(...)"`) are acceptable vanilla JS but prefer to move even those to the `{% block scripts %}` block.
- Use `&#8377;` for the rupee symbol in templates, never `&rupee;` or a literal `₹`. Use Python `f"{value:,.2f}"` then prefix `&#8377;` in the template.
- Use existing CSS variables (`--surface`, `--border-soft`, `--accent`, `--ink`, `--ink-soft`, `--ink-muted`, `--danger`). Zero hex literals in the new `/* Expenses */` block.
- `app.py` must continue to call `init_db()` and `seed_db()` on startup. Do not regress the bootstrap.
- Keep `debug=True`, `port=5001`. Do not change the dev server port.
- The navbar link to `/expenses` is only shown when `session.get("user_id")` is truthy. Signed-out users see only `Sign in` and `Get started` as today.
- The "Top category" tile on `/expenses` reflects the **filtered** subset, not all-time. The "Top category" tile on `/profile` (kept from step 04) reflects all-time. This is intentional: the management page is filtered (so the user can act on the same data they see), the dashboard is holistic.

## Definition of done

- [ ] Visiting `/expenses` while logged in as the demo user with no query string shows: 8 expenses in the list, `Top category: Shopping` (`&#8377;3,499.00 spent`), the filter card with `All time` chip active, and the add form pre-filled with today's date and the seven categories in the `<select>`.
- [ ] Submitting the add form with `amount=99, category=Food, date=2026-08-20, description="Test"` (all valid) inserts a row, flashes `Expense added.`, redirects to `/expenses`, and the new row is now visible in the list. Total expense count is 9.
- [ ] Submitting the add form with `amount=-5` (invalid) does **not** insert a row, flashes `Please enter a valid amount.`, redirects to `/expenses`, and the form is pre-filled with the user's bad input (so they don't retype everything).
- [ ] Submitting the add form with `category=Hacking` (not in `EXPENSE_CATEGORIES`) flashes `Please pick a category.` and does not insert.
- [ ] Submitting the add form with `date=garbage` flashes `Please enter a valid date (YYYY-MM-DD).` and does not insert.
- [ ] Visiting `/expenses?from=2026-08-05&to=2026-08-07` while logged in as the demo user shows: 3 expenses (the `2026-08-05`, `2026-08-06`, `2026-08-07` rows), `Top category: Entertainment` (`&#8377;599.00 spent`), the active-range caption `Active: 2026-08-05 → 2026-08-07`, and the `This month` chip is **not** active (this is a custom range, not the current month).
- [ ] Visiting `/expenses?from=2026-12-01&to=2026-12-31` while logged in as the demo user shows: empty list, `Top category: —`, `No expenses yet. Use the form above to add one.` placeholder.
- [ ] Clicking an expense's `Edit` link navigates to `/expenses?edit=<id>` (or to `/expenses?edit=<id>&from=...&to=...` from a filtered view) and the matching row renders its edit form pre-filled with the row's current values. Other rows render read-only. Submitting the edit form with valid input updates the row, flashes `Expense updated.`, and redirects to `/expenses` (preserving the `from` / `to`).
- [ ] Submitting the edit form with `amount=0` (invalid) does not update, flashes `Please enter a valid amount.`, redirects to `/expenses?edit=<id>` with the form pre-filled.
- [ ] Clicking an expense's `Delete` button (after `confirm()`) deletes the row, flashes `Expense deleted.`, and redirects to `/expenses`.
- [ ] Visiting `/expenses/<some-id>/edit` directly (e.g. by changing the URL) for an `id` that doesn't exist OR doesn't belong to the current user returns a 404 (not a 500, not a "permission denied" page).
- [ ] Visiting `/expenses/<id>/edit` and `/expenses/<id>/delete` via `GET` (typing the URL, not submitting a form) redirects to `/expenses` — these routes are POST-only.
- [ ] Visiting `/profile` while logged in as the demo user **no longer** shows the date filter (the `.profile-filter` block is gone) and shows all-time totals: `Total expenses 8` (or 9 if the test above added one), `Total spent ₹9,448.00` (or 9,547.00), `Top category Shopping`. The category bar chart and recent transactions stay.
- [ ] The navbar for a signed-in user shows `Hi, <name> | Expenses | Sign out`. Signed-out users see only `Sign in | Get started` (no `Expenses` link).
- [ ] Visiting `/expenses` while NOT logged in redirects (302) to `/login` with the flash `Please sign in to manage your expenses.`.
- [ ] `password_hash` is never SELECTed in any of the new queries. Grepping the rendered HTML for `pbkdf2`, `scrypt`, `password`, `werkzeug`, or `password_hash` returns nothing on both `/profile` and `/expenses`.
- [ ] All new and modified SQL uses `?` placeholders. Grepping `app.py` for SQL f-strings or `%` formatting inside SQL returns nothing.
- [ ] All new CSS uses existing CSS variables. The `/* Expenses */` block contains zero hex literals — `grep -n "#[0-9a-fA-F]\{3,6\}" static/css/style.css` shows the same set of hex literals as before this step.
- [ ] The rupee symbol appears as `&#8377;` in the template source, never as a literal `₹` character or `&rupee;`.
- [ ] `app.run(debug=True, port=5001)` starts cleanly. No new tracebacks on any of the paths above.
- [ ] No new pip packages installed (`pip freeze` is unchanged from before this step).
- [ ] All code paths that worked before this step (`/`, `/login`, `/register`, `/logout`, `/terms`, `/privacy`, `/profile` all-time) continue to behave correctly. `/profile` is intentionally simplified to its step 04 shape (no filter); this is a deliberate scope reduction, not a regression.
