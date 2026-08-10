# Spec: Profile Info

## Overview

The profile page added in step 04 (`feature/profile-page-design`, now merged) shows the user's identity plus two flat stats (expense count and total amount). It is functional but visually thin — a single card with two tiles and a sign-out button. This spec enriches `/profile` so it becomes a useful personal dashboard: identity on top, a 3-card summary row (count, total, top category), a recent-transactions list (latest 5 expenses with date, category, description, amount), and a minimalistic, sorted-by-amount category-bar chart built with plain HTML/CSS (no chart library). The view stays read-only — no editing, no transactions, no auth changes. The page must still read fluently even when a user has zero expenses (empty-state copy, not a stack trace).

## Depends on

- Step 01 — Database setup (`users` and `expenses` tables; `get_db()` helper).
- Step 02 — Registration (sets `session["user_id"]` / `session["user_name"]`; `app.secret_key` configured).
- Step 03 — Login and Logout (`_current_user()` helper, PRG `flash()` + `redirect()` pattern, auth-aware navbar).
- Step 04 — Profile Page Design (`profile()` view, `templates/profile.html`, `/* Profile */` CSS block already exist and will be extended in place — do not delete or replace working step 04 code; this step is purely additive).

## Routes

No new routes. The existing `GET /profile` handler in `app.py` is extended to compute the additional data and pass it to the (also extended) template.

- `GET /profile` — Authentication check unchanged from step 04. If logged in, additionally compute:
  1. **Top category** — the single `category` with the highest `SUM(amount)` for `user_id`. If there are no expenses yet, `top_category` is `None` (rendered as "—").
  2. **Recent transactions** — the 5 most recent expenses for `user_id`, ordered by `date DESC, id DESC` (newest first; tiebreak on `id` so expenses logged on the same day keep insertion order).
  3. **Category bar chart** — `category`, `SUM(amount)` for every category the user has at least one expense in, ordered by `SUM(amount) DESC`. Each row also computes `percentage = sum / grand_total * 100` so the bar widths can be rendered as percentages (with the largest category pinned to 100% of the track).

  Access level: **logged-in**. The current not-logged-in and stale-session branches (`_current_user() is None` and `user_row is None` → `session.clear()` + redirect) stay exactly as step 04 defined them.

## Database changes

No database changes. The `users` and `expenses` tables from step 01 (`database/db.py:43` and `database/db.py:55`) already have every column this step needs. All data is read via three additional SELECT queries against the existing schema, all parameterised.

## Templates

- **Modify:** `templates/profile.html` — Keep the existing user header (avatar + name + email + member-since) and the existing Card-based layout. Inside or below the existing `.profile-card`, add three new sections:
  1. **Summary row** — three tiles instead of the current two: `Total expenses`, `Total spent`, `Top category`. The "Top category" tile shows the category name (e.g. `Food`) and the amount below it in muted ink (`&#8377;4,829.00 spent`). When `top_category` is `None` (no expenses), the value shows `—` and the sub-line shows `&#8377;0.00 spent`.
  2. **Category bar chart** — a vertical stack of horizontal bars. Each row is one category with its name on the left, an amount label on the right (`&#8377;X,XXX.00`), and a thin track underneath whose filled portion is sized to the row's share of the grand total. Bars are sorted by amount descending (largest first). When the user has zero expenses, this section hides entirely (or renders a single muted "No expenses yet" line inside the card).
  3. **Recent transactions** — a list of up to 5 expense rows. Each row shows: `date` (YYYY-MM-DD), `category` (small uppercase chip), `description` (or a muted "—" if empty), and the amount on the right (`&#8377;X,XXX.00`). When the user has zero expenses, this section shows a muted "No transactions yet" placeholder. The list is visually capped at 5 rows; pagination is out of scope for this step.

  Keep the existing "Sign out" button at the bottom of the page. The page title (`Your profile — Spendly`) is unchanged.

- **Modify:** `static/css/style.css` — Append a new `/* Profile Info */` block at the bottom (after the existing `/* Profile */` block). All colors via existing CSS variables. No edits to existing rules.

## Files to change

- `app.py` — Extend the `profile()` view with three additional SELECT queries (top category, recent 5, category totals). All queries go through the same `get_db()` connection that's already opened in step 04 (no second connection). Computed display values (formatted INR strings, percentages, "Unknown" fallback for `None` `created_at`) are computed in Python before rendering. The existing branches (not logged in, stale session) are unchanged.
- `templates/profile.html` — Add the three new sections described above. Existing header + sign-out stay. Iterate over `recent_transactions` and `category_totals` Jinja-side.
- `static/css/style.css` — Append a `/* Profile Info */` block. New classes only; do not redefine existing styles.

## Files to create

None. All changes are edits to existing files.

## New dependencies

No new dependencies. The chart is plain HTML/CSS (flexbox or grid + width: x%), no Chart.js, no D3, no new pip packages. The Jinja2 `|length` filter (already loaded with Flask) is enough for empty-state checks.

## Rules for implementation

- No SQLAlchemy or ORMs. Use `sqlite3` directly via `database.db.get_db()`.
- Parameterised queries only — every new SELECT must use `?` placeholders. No f-strings, no `%` formatting inside SQL.
- The `profile()` view is **GET-only**. Do not add `methods=["POST"]`.
- Re-use the existing `_current_user()` helper from step 03. Do not introduce a second source of truth for login state.
- Keep the existing not-logged-in and stale-session branches exactly as step 04 wrote them. Do not move the `session.clear()` call, do not change the flash strings in those branches.
- Never expose `password_hash` to the template. The `user` payload stays as step 04 defined it (`id`, `name`, `email`, `created_at` only).
- Amounts must be formatted as INR with the `&#8377;` rupee symbol (do **not** use `&rupee;`, which is not a valid HTML entity). Use Python `f"{value:,.2f}"` then prefix `&#8377;` in the template, OR pre-format in Python and pass a string. The display format is identical to step 04 (`&#8377;X,XXX.00`).
- Dates must be rendered as `YYYY-MM-DD` only (no time). `sqlite3` returns `created_at` and `date` as strings; slice the first 10 characters in Python before passing to the template, the same way step 04 already does for `member_since`.
- `top_category` computation: `SELECT category, SUM(amount) AS total FROM expenses WHERE user_id = ? GROUP BY category ORDER BY total DESC LIMIT 1`. If the user has zero expenses, the query returns no rows — `top_category` is `None` and the template shows `—`. Do not call `SUM` over zero rows and rely on `None` appearing as a string; if the no-expenses case is detected (e.g. via a separate `COUNT(*)` check), skip the top-category query entirely.
- Recent transactions: `SELECT id, date, category, description, amount FROM expenses WHERE user_id = ? ORDER BY date DESC, id DESC LIMIT 5`. Always returns 0–5 rows. Empty list renders the "No transactions yet" placeholder.
- Category totals: `SELECT category, SUM(amount) AS total FROM expenses WHERE user_id = ? GROUP BY category ORDER BY total DESC`. Iterate over the result in Jinja in the order returned (already descending). Compute `percentage = total / grand_total * 100` in Python before rendering, where `grand_total` is the sum of all `total` values (or `1` if there are none, to avoid division by zero — but the empty-state case is rendered separately, so this branch should never fire).
- The bar chart's filled portion is sized via `width: X%` inline style where X is the percentage. The largest category is by definition 100% of the track — the chart's visual hierarchy is preserved without any normalization step.
- The bar chart uses existing CSS variables for colors: tracks use `--border-soft`, fills use `--accent` (or a per-category color if the existing palette defines one — reuse existing palette values, do not add new hex literals). Labels use `--ink-soft` and `--ink-muted`.
- All new CSS lives in the appended `/* Profile Info */` block. Do not modify the existing `/* Profile */` block.
- All templates extend `base.html`. Per-page JS (if any) goes in `{% block scripts %}`. This step does not need new JS.
- `app.py` must continue to call `init_db()` and `seed_db()` on startup as it does today — do not regress the bootstrap.
- Keep `debug=True`, `port=5001`. Do not change the dev server port.
- For the demo user (`demo@spendly.com` / `demo123`, seeded in step 01), the page should show: 8 expenses, total `&#8377;9,448.00`, top category `Food` (`250 + 780 = 1030`), and a category bar chart sorted by `Bills (1850) > Shopping (3499) > Transport (1200) > Food (1030) > Entertainment (599) > Health (450) > Other (320)` — wait, that's the wrong order. Recompute: the eight seed amounts are `Food 250, Transport 1200, Bills 1850, Shopping 3499, Entertainment 599, Health 450, Other 320, Food 780`. Category totals: `Shopping 3499, Bills 1850, Transport 1200, Food 1030, Entertainment 599, Health 450, Other 320`. Bars must appear in that exact order. The "Top category" tile must show `Shopping`.

## Definition of done

- [ ] Visiting `/profile` while logged in as the demo user shows:
  - Identity header unchanged from step 04 (avatar `D`, "Hi, Demo User", email, member-since YYYY-MM-DD).
  - Summary row with three tiles: `Total expenses` → `8`, `Total spent` → `₹9,448.00`, `Top category` → `Shopping` with `₹3,499.00 spent` subtitle.
  - Category bar chart with 7 rows in descending order: `Shopping ₹3,499.00`, `Bills ₹1,850.00`, `Transport ₹1,200.00`, `Food ₹1,030.00`, `Entertainment ₹599.00`, `Health ₹450.00`, `Other ₹320.00`. The largest bar (`Shopping`) fills 100% of the track; the rest are sized proportionally.
  - Recent transactions list with 5 rows, newest first. The newest seeded expense is `2026-08-08` (`Food / Groceries / ₹780.00`). Each row shows date, category, description, amount.
  - Sign-out button still works.
- [ ] Visiting `/profile` while NOT logged in redirects (302) to `/login` with the step 04 flash `Please sign in to view your profile.`. The new code does not change this behavior.
- [ ] Visiting `/profile` while logged in as a user with **zero** expenses (e.g. the new user created via `/register`) renders gracefully: identity header still shows, count tile shows `0`, total tile shows `₹0.00`, top category tile shows `—`, the category bar chart row is replaced with `No expenses yet`, the recent transactions list shows `No transactions yet`. No 500, no `None` literal anywhere in the rendered HTML.
- [ ] The `password_hash` column is never SELECTed in the new queries and never reaches the template. Grepping the rendered HTML for `pbkdf2`, `scrypt`, `password`, `werkzeug`, or `password_hash` returns nothing.
- [ ] All three new SELECT queries use `?` placeholders. Grepping `app.py` for SQL f-strings or `%` formatting inside SQL returns nothing new.
- [ ] All new CSS uses existing CSS variables. The `/* Profile Info */` block contains zero hex literals — `grep -n "#[0-9a-fA-F]\{3,6\}" static/css/style.css` shows the same set of hex literals as before this step.
- [ ] The rupee symbol appears as `&#8377;` in the template source, never as a literal `₹` character.
- [ ] `app.run(debug=True, port=5001)` starts cleanly. No new tracebacks on any of the paths above.
- [ ] No new pip packages installed (`pip freeze` is unchanged from before this step).
- [ ] All code paths that touched step 04 (`/profile` view, `templates/profile.html`, navbar greeting, login/logout flow, `_current_user()` helper) continue to behave identically when this step is layered on top.
