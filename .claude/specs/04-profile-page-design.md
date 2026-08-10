# Spec: Profile Page Design

## Overview

Step 04 turns the `/profile` placeholder (currently a plain string `"Profile page — coming in Step 4"`) into a real read-only profile page that authenticated users land on after registering or signing in. The page reads the logged-in user's `name`, `email`, and `created_at` from the `users` table, also shows the count and total of their expenses from the `expenses` table so the profile feels useful at a glance, and provides a clean sign-out entry point. This step is purely a view + DB read — no profile editing, no password change, no expense mutation. Those land in later steps.

## Depends on

- Step 01 — Database setup (`users` table with `name`, `email`, `password_hash`, `created_at`; `expenses` table with `user_id`, `amount`; `get_db()` helper).
- Step 02 — Registration (sets `session["user_id"]` / `session["user_name"]`; uses `flash()` + redirect; defines `app.secret_key`).
- Step 03 — Login and Logout (defines `_current_user()` helper, `logout()` view, and the auth-aware navbar in `base.html`; redirects `/` to `/profile` when logged in).

## Routes

- `GET /profile` — Read-only. Requires `session["user_id"]`. Look up the user by `id`; if found, render `profile.html` with their `name`, `email`, `created_at`, plus an expense count and total amount. If no row matches the session id (e.g. user deleted between sessions), clear the session and redirect to `/login` with a flash. Access level: **logged-in**.

No new POST routes. Editing / deleting the account is out of scope for this step.

## Database changes

No database changes. Both tables created in Step 01 (`database/db.py:43` and `database/db.py:55`) already have every column this step needs.

This step reads:

- `users` → `id`, `name`, `email`, `created_at` (`SELECT id, name, email, created_at FROM users WHERE id = ?`)
- `expenses` → `COUNT(*)`, `SUM(amount)` (`SELECT COUNT(*), COALESCE(SUM(amount), 0) FROM expenses WHERE user_id = ?`)

## Templates

- **Create:** `templates/profile.html` — Authenticated profile page with avatar (initial), name, email, member-since date, a 2-card stats row (expense count, total spent), and a "Sign out" link. Extends `base.html`.
- **Modify:** `templates/base.html` — No structural change required. The existing navbar already branches on `session.get("user_id")` and shows "Hi, <name>" / "Sign out". The profile page may add a secondary `Hi, <name>` heading of its own; the navbar greeting stays as-is.

## Files to change

- `app.py` — Replace the `profile()` placeholder string with a GET-only handler that:
  1. Pulls `user_id` from `session` via `_current_user()`. If `None`, redirect to `/login` with a flash (`"Please sign in to view your profile."`).
  2. Opens a connection via `database.db.get_db()`, fetches `SELECT id, name, email, created_at FROM users WHERE id = ?`, and a second query `SELECT COUNT(*) AS n, COALESCE(SUM(amount), 0) AS total FROM expenses WHERE user_id = ?`.
  3. If the user row is `None`, clear the session and redirect to `/login` with a flash (`"Your account could not be found. Please sign in again."`).
  4. Passes the row + stats to `render_template("profile.html", user=user, expense_count=..., expense_total=...)`.
- `static/css/style.css` — Append a new `/* Profile */` section at the bottom (after the existing `video-modal` block) with classes used by `profile.html`. All colours via CSS variables. **No modifications** to existing rules.

## Files to create

- `templates/profile.html` — New template. See "Templates" above.

## New dependencies

No new dependencies. Uses `sqlite3` (stdlib), existing `werkzeug.security` is not needed on this step (we don't hash or verify anything), and Flask's `session` / `flash` are already imported in `app.py`.

## Rules for implementation

- No SQLAlchemy or ORMs. Use `sqlite3` directly via `database.db.get_db()`.
- Parameterised queries only — both `SELECT` statements must use `?` placeholders. No f-strings or `%` formatting inside SQL.
- The `profile()` view is **GET-only**. Do not add `methods=["POST"]`. Editing the profile is a later step.
- Re-use the existing `_current_user()` helper from Step 03 instead of reading `session.get("user_id")` inline. Do not introduce a second source of truth for "is the user logged in".
- Use the same `flash()` + `redirect(url_for(...))` PRG pattern as Steps 02 and 03 when the session is missing or stale.
- Never expose `password_hash` to the template — only pass `id`, `name`, `email`, `created_at`. The `user` dict in the template context must not contain `password_hash`.
- Amounts must be formatted as INR with the `&#8377;` rupee symbol. Do **not** use `&rupee;` (not a valid HTML entity). Format to 2 decimal places (e.g. `&#8377;1,250.00`). Use Python `f"{value:,.2f}"` then prefix `&#8377;` in the template, OR pre-format in Python and pass a string.
- `created_at` is a SQLite `datetime('now')` string (UTC, e.g. `2026-08-10 14:32:11`). Render only the date portion (`YYYY-MM-DD`) in the profile. Strip the time — do not display seconds. If the value is `None` for any reason, show `"Unknown"` rather than crashing.
- Avatar shows the user's first initial in a circle. Use the user's `name[0].upper()`. If `name` is empty (shouldn't happen due to Step 02 validation, but be defensive), use `"?"`.
- Use CSS variables from `static/css/style.css` for any new colours. Do not hardcode hex values in `style.css` or inline styles.
- All templates extend `base.html`. Per-page JS (if any) goes in `{% block scripts %}`. This step does not need new JS.
- `app.py` must continue to call `init_db()` and `seed_db()` on startup as it does today — do not regress the bootstrap.
- Keep `debug=True`, `port=5001`. Do not change the dev server port.
- For the demo user (`demo@spendly.com` / `demo123`, seeded in Step 01), the profile should show `8` expenses and a non-zero total (`₹9,448.00` from the seed data). Use this to sanity-check the page.

## Definition of done

- [ ] Visiting `/profile` while logged in renders `profile.html` with the user's `name`, `email`, and member-since date (date only, no time).
- [ ] Visiting `/profile` while NOT logged in redirects (302) to `/login` and flashes `"Please sign in to view your profile."`. The login form surfaces the flash on the next GET.
- [ ] The "password_hash" column is never sent to the template — inspecting the rendered HTML or the template context does not reveal any hash, plaintext password, or werkzeug prefix.
- [ ] After the demo user (`demo@spendly.com` / `demo123`) logs in, the profile shows `8` expenses and a total of `₹9,448.00` (sum of the seeded amounts: 250+1200+3499+1850+599+450+320+780).
- [ ] When the session's `user_id` does not match any row in `users`, the session is cleared and the user is redirected to `/login` with a flash. No 500.
- [ ] The "Sign out" link on the profile page routes through `/logout` (the existing Step 03 view) and clears the session. After signing out, visiting `/profile` redirects to `/login`.
- [ ] Avatar shows the first letter of the user's name, uppercase, in a circle. For `Demo User`, the avatar shows `D`.
- [ ] `app.run(debug=True, port=5001)` still starts cleanly. Visiting `http://127.0.0.1:5001/profile` while logged in renders without tracebacks.
- [ ] No raw SQL string formatting anywhere in `app.py` — every `execute()` uses `?` placeholders.
- [ ] No new pip packages installed (`pip freeze` is unchanged from before this step).
- [ ] All new CSS uses CSS variables from `static/css/style.css` — no hardcoded hex values in the new `Profile` block.
- [ ] `created_at` is rendered as `YYYY-MM-DD` (date only), not the full datetime string. The character `₹` appears as `&#8377;` in the template source.