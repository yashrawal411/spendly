# Spec: Add Expense on Profile Page

## Overview

Until now, the user can only view their spending on `/profile` — the page is read-only. Step 06 turns the profile page into the **single place** to record a new expense by replacing the placeholder `/expenses/add` route with a real form-and-POST handler and by surfacing that form directly on `/profile`. The form lives in a card on the profile page so a user can log a chai-and-samosa and immediately see it in the "Recent transactions" list and the summary tiles without navigating away. The existing date-range filter (step 05) must keep working: the form posts to `/expenses/add`, the new row lands in the DB, and the user is redirected back to `/profile` (preserving whatever `from`/`to` filter was active). Editing and deleting individual expenses stay out of scope — those are future steps.

## Depends on

- Step 01 — Database setup (`expenses` table with `amount`, `category`, `date`, `description` columns; `get_db()` helper).
- Step 02 — Registration (`session["user_id"]`).
- Step 03 — Login and Logout (`_current_user()`, PRG flash pattern).
- Step 04 — Profile Page Design (`/profile` route, `templates/profile.html`, summary tiles, recent transactions list, category bar chart, `/* Profile Info */` CSS block).
- Step 05 — Date Filter on Profile Page (`?from=&to=` filter, the `.profile-filter` card, PRG flash pattern reused here for validation errors).
- Step 05 (placeholder route) — `GET /expenses/add` currently returns a placeholder string at `app.py:306-308`. This step replaces that handler with a real GET+POST implementation and removes the placeholder text.

## Routes

- `GET|POST /expenses/add` — logged-in only. **Replaces** the existing stub. Behaviour:
  1. **Auth:** `_current_user() is None` → flash `Please sign in to add an expense.` and redirect to `/login`. Unauthenticated POSTs get the same treatment (do not 405; do not 500; redirect them through the login flow).
  2. **GET:** render `templates/add_expense.html` with any flashed validation error (`error=flashed[0] if flashed else None`), the current user's name (for the "logging in as" line, optional), and pre-filled defaults: today's date (`date.today().isoformat()`) and an empty `amount`. No DB reads required for the GET.
  3. **POST:** read `amount`, `category`, `date`, `description` from `request.form`. Validate per the rules below. On any validation failure, **flash** the first error and **redirect** to `/expenses/add` (PRG pattern; the GET branch re-reads the flash and re-renders the form). On success: insert a row into `expenses` with `user_id = session["user_id"]`, then redirect to `/profile` (no query string) so the user lands on the unfiltered view with the new row in `Recent transactions`.
  4. **Return-URL behaviour:** if the form was submitted from a filtered profile page (`/profile?from=…&to=…`), the form's hidden `next` field carries that URL; after a successful insert, redirect there instead of `/profile`. The field is a plain string, validated to start with `/profile` (no open-redirect via an absolute URL or `//evil.example`). On a GET, the form echoes the `next` value into the hidden input so a validation round-trip preserves it. A missing or invalid `next` falls back to `/profile`.

  Access level: **logged-in**. Stale session (`user_id` set but the user no longer exists) clears the session and redirects to `/login` with the existing `Your account could not be found.` flash.

- `GET /expenses/add` (the existing stub at `app.py:306-308`) — **removed** in this step. The new handler subsumes both verbs.

No other routes change. `/expenses/<int:id>/edit` and `/expenses/<int:id>/delete` remain placeholders for future steps.

## Database changes

No database changes. The `expenses` table already has all the columns the form writes to (`amount`, `category`, `date`, `description`, `user_id`) per `database/db.py:53-66`. The new insert is a single `INSERT INTO expenses …` statement against the existing schema.

## Templates

- **Create:** `templates/add_expense.html` — a standalone form page that extends `base.html`. Contents:
  1. A page header (`<h1>Add an expense</h1>` and a one-line subtitle).
  2. A `<form method="post" action="/expenses/add">` with:
     - A hidden `<input type="hidden" name="next" value="{{ next_url or '/profile' }}">` so the return URL survives the POST.
     - `Amount (&#8377;)` label + `<input type="number" name="amount" step="0.01" min="0.01" required value="{{ amount|default('') }}">`.
     - `Category` label + `<select name="category" required>` populated from a fixed list (`Food`, `Transport`, `Shopping`, `Bills`, `Entertainment`, `Health`, `Other`) — `Other` is the default. The list is passed in by the view, not hard-coded twice in template + view.
     - `Date` label + `<input type="date" name="date" required value="{{ date|default(today) }}">` where `today` is today's date in `YYYY-MM-DD`.
     - `Description (optional)` label + `<input type="text" name="description" maxlength="200" value="{{ description|default('') }}">`.
     - A primary "Add expense" submit button and a secondary "Cancel" link back to `{{ next_url or '/profile' }}`.
  3. Below the form, a single error line rendering `{{ error }}` only when set (matches the pattern used by `login.html` / `register.html`).

- **Modify:** `templates/profile.html` — Above the existing `.profile-stats` block (and above the existing `.profile-filter` block, so the form sits at the top of the page and feels like the primary action), insert an `.profile-add-expense` card containing:
  1. A short heading (`Add an expense`) and a one-line subtitle.
  2. A `<form method="get" action="/expenses/add">` (GET — navigates to the standalone form page) with:
     - A hidden `<input type="hidden" name="next" value="{{ request.full_path }}">` so the standalone form knows where to send the user back.
     - Three visible fields: `Amount`, `Category` (select, defaults to `Other`), `Date` (defaults to today).
     - A "Add expense" submit button.
  3. No `Description` field on the profile-page shortcut — description is collected on the standalone page. This keeps the profile-page card visually compact.

  The form does **not** POST from the profile page. The "Add expense" button is a GET navigation to `/expenses/add`; the actual insert happens on the standalone page. This is the simplest path that keeps the profile page's data flow GET-only (as the date-filter spec required) and matches the existing pattern in `landing.html` where the "Get started" CTA navigates to `/register` rather than submitting a form inline.

- **Modify:** `static/css/style.css` — Append two new blocks at the bottom:
  1. `/* Add Expense Form */` — styles for `templates/add_expense.html`: form container, labels, inputs, select, primary submit, secondary cancel link, error line. Reuse existing variables (`--paper-card`, `--border`, `--border-soft`, `--radius-md`, `--radius-sm`, `--accent`, `--accent-light`, `--ink`, `--ink-soft`, `--ink-muted`, `--font-body`). No hex literals.
  2. `/* Profile Add Expense */` — styles for the `.profile-add-expense` card on `templates/profile.html`: compact form layout (three fields inline on wide screens, stacked on narrow), a "quick add" feel that's visually lighter than the full standalone form. Reuse the same variables. No hex literals.

## Files to change

- `app.py` —
  1. Replace the existing `add_expense()` stub (currently `app.py:306-308`) with a real handler that accepts both `GET` and `POST`. Implement the validation, the PRG flash on failure, the `INSERT` on success, and the `next`-URL handling described under **Routes**.
  2. Add a small `_validate_expense_form(amount_raw, category_raw, date_raw, description_raw) -> str | None` helper that returns the first error message or `None`. Same shape as the existing `_validate_registration` helper.
  3. Add a small `_safe_next_url(raw_next) -> str` helper that returns `raw_next` only if it starts with `/profile` (or is empty), else falls back to `/profile`. Defends against open-redirect.
  4. The category list (`["Food", "Transport", "Shopping", "Bills", "Entertainment", "Health", "Other"]`) lives as a module-level constant in `app.py` and is passed to `add_expense.html` and to the profile-page card. Single source of truth.

- `templates/profile.html` — Insert the `.profile-add-expense` card above the existing `.profile-filter` block. Pass `request.full_path` as the `next` value. The existing `.profile-filter` and everything below it stay byte-for-byte identical.

- `static/css/style.css` — Append `/* Add Expense Form */` and `/* Profile Add Expense */` blocks. New classes only; no edits to existing rules.

## Files to create

- `templates/add_expense.html` — The standalone add-expense form (extends `base.html`, shows a heading + form + cancel link + error line).

## New dependencies

No new dependencies. The form is plain HTML; no JS; no new pip packages. `date` is already imported in `app.py` (from step 05).

## Rules for implementation

- No SQLAlchemy or ORMs. Use `sqlite3` directly via `database.db.get_db()`. The insert is one statement: `INSERT INTO expenses (user_id, amount, category, date, description) VALUES (?, ?, ?, ?, ?)` with all five values as bound parameters.
- Parameterised queries only — no f-strings or `%` formatting inside SQL.
- Re-use the existing `_current_user()` helper from step 03. Do not introduce a second source of truth for login state.
- The new handler must **own** its DB connection: `conn = get_db()` … `conn.close()` in a `finally:` block. The `commit()` happens before `close()`. On the rare `sqlite3.IntegrityError` (e.g. an FK violation if the user_id is stale), rollback, flash a generic "Could not save your expense. Please try again.", and redirect to `/expenses/add`.
- The new handler runs **`init_db()` and `seed_db()` on startup** (already done at module top — do not regress that). No additional bootstrap is needed.
- The form on `templates/profile.html` is **GET-only**. It is a navigation shortcut, not a POST target. The actual insert happens on `templates/add_expense.html`. This keeps the profile page's data flow GET-only (matching step 05) and avoids a hidden gotcha where the date-filter `?from=&to=` query string would be lost on a POST-back from the profile page.
- The category list is a module-level constant in `app.py` (e.g. `EXPENSE_CATEGORIES = ("Food", "Transport", "Shopping", "Bills", "Entertainment", "Health", "Other")`). Both templates receive it from the view — never hard-code the list in Jinja.
- Validation rules in `_validate_expense_form`:
  1. `amount_raw` must be present, parse as `float`, and be `> 0`. Maximum 12 digits before the decimal point (sanity cap, prevents `1e308` shenanigans). Error: `Enter a valid amount greater than zero.`
  2. `category_raw` must be present **and** be one of `EXPENSE_CATEGORIES`. Error: `Choose a category.` (Rejects free-text category injection; the form's `<select>` already constrains this but the view must not trust the client.)
  3. `date_raw` must parse as `datetime.strptime(date_raw, "%Y-%m-%d")`. Error: `Enter a valid date (YYYY-MM-DD).`
  4. `description_raw` is optional. If present, trim and cap at 200 characters (matches the `maxlength` on the input). Stored as-is (empty string is fine; the column is `TEXT` and nullable, but we always write a string).
  5. First error wins — same pattern as `_validate_registration`.
- The view converts the validated `amount` to `float` and the validated `date` to its `YYYY-MM-DD` string before the INSERT. The view does **not** re-format the date — it just passes the string the user submitted (after `strptime` validation).
- The standalone form's `date` default is `date.today().isoformat()`. The profile-page shortcut's `date` default is also today. A user posting without touching the date gets today's row.
- The standalone form's `next` handling:
  - On GET, `request.args.get("next")` is read, run through `_safe_next_url`, and echoed into the hidden input.
  - On POST, `request.form.get("next")` is read, run through `_safe_next_url`, and used as the post-insert redirect target.
  - `_safe_next_url` returns `/profile` if the value is missing, empty, or doesn't start with `/profile` (single leading slash only — reject `//evil.example`, `http://…`, scheme-relative URLs).
- The "Cancel" link on the standalone form also uses the safe `next` URL, so cancelling a flow that started on a filtered profile page returns the user to that same filter.
- All templates extend `base.html`. The standalone form uses `{% block content %}`; it does not need a `{% block scripts %}` block (no per-page JS).
- `app.py` must continue to run with `debug=True, port=5001`. Do not change the dev server port.
- All amounts formatted as INR with the `&#8377;` rupee symbol (no `&rupee;`, no literal `₹`). Dates as `YYYY-MM-DD`. The standalone form's amount input is a plain `<input type="number">` — no formatting in the field, only on the profile page where the new row is rendered into the existing recent-transactions table.
- No CSS hex literals. All new rules use the existing CSS custom-property palette.

## Definition of done

- [ ] `GET /expenses/add` while logged in renders the standalone add-expense form. The form contains `Amount`, `Category`, `Date`, `Description`, an "Add expense" submit, and a "Cancel" link. The date field defaults to today. The category `<select>` lists `Food`, `Transport`, `Shopping`, `Bills`, `Entertainment`, `Health`, `Other` with `Other` selected.
- [ ] `POST /expenses/add` while logged in with valid form data inserts a row into `expenses` with the submitted values and the logged-in `user_id`, then redirects (302) to `/profile` (or to `next` if supplied and safe). The new row is visible in the "Recent transactions" list on `/profile`.
- [ ] `POST /expenses/add` while NOT logged in redirects (302) to `/login` with the flash `Please sign in to add an expense.`. No row is inserted. No 500.
- [ ] `POST /expenses/add` while logged in with `amount=""` redirects (302) to `/expenses/add` with the flash `Enter a valid amount greater than zero.`. The GET branch renders the form with the error visible. No row is inserted.
- [ ] `POST /expenses/add` while logged in with `amount=0` redirects (302) to `/expenses/add` with the same error. No row is inserted.
- [ ] `POST /expenses/add` while logged in with `amount=-5` redirects (302) to `/expenses/add` with the same error. No row is inserted.
- [ ] `POST /expenses/add` while logged in with `category=NotInTheList` redirects (302) to `/expenses/add` with the flash `Choose a category.`. No row is inserted. (The `<select>` doesn't allow this, but a curl-style POST does.)
- [ ] `POST /expenses/add` while logged in with `date=garbage` redirects (302) to `/expenses/add` with the flash `Enter a valid date (YYYY-MM-DD).`. No row is inserted.
- [ ] `POST /expenses/add` while logged in with `next=https://evil.example/` redirects (302) to `/profile`, not to evil.example. (Open-redirect defence.)
- [ ] `POST /expenses/add` while logged in with `next=//evil.example/` redirects (302) to `/profile`, not to evil.example.
- [ ] `POST /expenses/add` while logged in with `next=/profile?from=2026-08-01&to=2026-08-15` redirects (302) to that exact URL. The user lands on the filtered profile page with the new row visible (if it falls in range) or absent (if it doesn't).
- [ ] `GET /profile` while logged in shows the new `.profile-add-expense` card above the existing `.profile-filter` card. The card's form is a GET to `/expenses/add` with a hidden `next` field carrying the current `request.full_path` (so on `/profile?from=2026-08-01&to=2026-08-15`, `next` is `/profile?from=2026-08-01&to=2026-08-15`).
- [ ] Submitting the profile-page shortcut form with `amount=42, category=Food, date=2026-08-15` navigates to `/expenses/add?amount=42&category=Food&date=2026-08-15&next=…` and the standalone form pre-fills those values.
- [ ] The new `.profile-add-expense` card does not regress the existing `.profile-filter` card, the summary tiles, the category bar chart, or the recent transactions list. The page renders cleanly with both cards present.
- [ ] The `app.py` placeholder text `Add expense — coming in Step 7` is gone — `grep -n "coming in Step 7" app.py` returns nothing.
- [ ] `password_hash` is never SELECTed in the new handler. The INSERT only writes to `expenses`, never to `users`. Grepping the new code for `password_hash` returns nothing.
- [ ] The new INSERT uses `?` placeholders. No SQL f-strings or `%` formatting inside SQL.
- [ ] The new CSS blocks (`/* Add Expense Form */` and `/* Profile Add Expense */`) contain zero hex literals — `grep -n "#[0-9a-fA-F]\{3,6\}" static/css/style.css` shows the same set of hex literals as before this step.
- [ ] The rupee symbol appears as `&#8377;` in the template sources (`add_expense.html`, `profile.html`), never as a literal `₹` character.
- [ ] `app.run(debug=True, port=5001)` starts cleanly. No new tracebacks on any of the paths above.
- [ ] No new pip packages installed (`pip freeze` is unchanged from before this step).
- [ ] Every page that worked before this step (`/`, `/login`, `/register`, `/logout`, `/terms`, `/privacy`, `/profile` unfiltered, `/profile` filtered, the existing `GET /expenses/add` placeholder) continues to behave correctly. The only behavioural change to the placeholder route is that `GET /expenses/add` now renders the real form instead of the string `Add expense — coming in Step 7`.
