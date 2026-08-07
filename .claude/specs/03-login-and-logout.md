# Spec: Login and Logout

## Overview

Step 03 turns the existing `/login` template into a real sign-in flow and replaces the `/logout` placeholder with a working session-clearing endpoint. Once this step lands, a registered user can sign in with email + password, gets a `session` populated with their `user_id` and `user_name`, and lands on `/profile`. From any authenticated page, clicking "Sign out" hits `/logout`, clears the session, and redirects back to `/login`. Login errors (wrong email, wrong password, missing fields) are rendered inside the auth card with the same Post/Redirect/Get pattern used for registration in Step 02. A small logged-in-vs-logged-out signal is added to the navbar so users can see their state at a glance.

## Depends on

- Step 01 — Database setup (`users` table; `password_hash` column; `get_db()` helper).
- Step 02 — Registration (sets `session["user_id"]` / `session["user_name"]` on register; uses `flash()` + redirect for error UX; defines `app.secret_key` so `flask.session` works).

## Routes

- `POST /login` — Validate `email` and `password` from the form. Lookup the user by lowercased email. If the user exists and `check_password_hash` returns `True`, set `session["user_id"]` and `session["user_name"]`, redirect to `/profile`. Otherwise flash a generic "Invalid email or password." and redirect back to `/login`. Access level: **public**.
- `GET /login` — Render `login.html`. If a previous POST error was flashed, surface it inside the auth card (same pattern as `register.html` already uses).
- `GET /logout` — Clear `session` (set it to an empty dict), redirect to `/login`. Access level: **logged-in** (visiting `/logout` while logged out is a no-op redirect — see Rules).
- `GET /` — If the user is logged in (i.e. `session.get("user_id")` is set), redirect to `/profile` instead of rendering the landing page. This is the "auth-aware landing" rule. Access level: **public** (the route is public; the redirect only changes the destination for authenticated users).

## Database changes

No database changes. The `users` table from Step 01 (`database/db.py:43`) is sufficient. Authentication is `SELECT id, name, password_hash FROM users WHERE email = ?` followed by `check_password_hash(user["password_hash"], submitted_password)`.

## Templates

- **Modify:** `templates/login.html` — already has the `{% if error %}<div class="auth-error">{{ error }}</div>{% endif %}` block (same pattern as `register.html`). No template change needed if the view passes `error=` correctly. **No new field** — login form already has `email` and `password` only.
- **Modify:** `templates/base.html` — Replace the navbar's static "Sign in / Get started" pair with a small Jinja conditional that branches on `session.get("user_id")`:
  - Not logged in → `<a href="/login">Sign in</a> <a href="/register" class="nav-cta">Get started</a>` (current behaviour).
  - Logged in → `<span class="nav-greeting">Hi, {{ session["user_name"] }}</span> <a href="/logout">Sign out</a>`. No CTA link, no "Sign in" link.

## Files to change

- `app.py` — Replace the `login()` view with a GET/POST handler that validates, looks up the user by email, verifies the password, sets `session`, and redirects. Use the same `flash()` + redirect PRG pattern as `register()`. Add `logout()` view that clears `session` and redirects to `/login`. Add a tiny helper `_current_user()` that returns `session.get("user_id")` or `None` so the landing route and the navbar logic share one source of truth. Modify the `landing()` view to redirect to `/profile` when `_current_user()` is truthy. Add `from werkzeug.security import check_password_hash` to the imports.
- `templates/base.html` — Add the Jinja conditional in the navbar links area so the header reflects login state.

## Files to create

None.

## New dependencies

No new dependencies. `werkzeug.security.check_password_hash` is already in `requirements.txt` (used implicitly by anything depending on werkzeug's password helpers).

## Rules for implementation

- No SQLAlchemy or ORMs. Use `sqlite3` directly via `database.db.get_db()`.
- Parameterised queries only — every `SELECT` / `INSERT` must use `?` placeholders. No f-strings or `%` formatting inside SQL.
- Passwords must be verified with `werkzeug.security.check_password_hash`. Never compare hashes with `==`; never store plaintext; never log the submitted password.
- The login error message must be **generic** — "Invalid email or password." — whether the email doesn't exist or the password is wrong. This prevents account-enumeration via the login form.
- Triple-email lookup rule: lowercase the submitted email (`email.strip().lower()`) before the `SELECT` so it matches the lowercased value stored in Step 02. Do NOT lowercase the password field.
- Use the same `flash()` + `redirect(url_for(...))` PRG pattern from Step 02's registration. The GET handler reads the flash via `get_flashed_messages()` and passes the first message as `error=`.
- The `logout()` view must be safe to call when the user is already logged out — it should not raise. Calling `session.clear()` on an empty session is a no-op.
- POST handlers must always redirect after success (avoid the browser refresh-re-POST loop); GET handlers must always re-render (no side effects).
- The navbar's auth-aware logic must work without any extra query — it should branch purely on `session.get("user_id")`. The `user_name` for the greeting is also read from the session, not from a DB lookup.
- Use CSS variables from `static/css/style.css` for any new colours. Do not hardcode hex values.
- All templates extend `base.html` and use the existing `{% block content %}` block.
- `app.py` must continue to call `init_db()` and `seed_db()` on startup as it does today — do not regress the bootstrap.
- The login POST must not 405 — the existing `login()` view is GET-only with `methods=["GET"]` (the default for a single-method Flask route). Convert it to `methods=["GET", "POST"]`.

## Definition of done

- [ ] Submitting `POST /login` with a known email + correct password (`demo@spendly.com` / `demo123` from the seed) sets `session["user_id"]` and `session["user_name"]` and redirects (302) to `/profile`.
- [ ] Submitting `POST /login` with a wrong password shows "Invalid email or password." inside the auth card and does NOT set any session keys.
- [ ] Submitting `POST /login` with a non-existent email shows the same generic error message (no enumeration leak).
- [ ] Submitting a missing email or password shows the error and sets no session.
- [ ] Immediately refreshing the browser after a failed login POST renders a clean form (Post/Redirect/Get — no error persists on refresh).
- [ ] After successful login, the navbar shows "Hi, <name>" and a "Sign out" link instead of "Sign in" / "Get started".
- [ ] Visiting `/logout` (while logged in) clears the session and redirects to `/login`. The navbar then shows "Sign in" / "Get started" again.
- [ ] Visiting `/logout` while logged out is a no-op that redirects to `/login` without raising.
- [ ] Visiting `/` while logged in redirects to `/profile`; visiting `/` while logged out renders the landing page as before.
- [ ] `app.run(debug=True, port=5001)` still starts cleanly. No new tracebacks on any of the routes above.
- [ ] No raw SQL string formatting anywhere in `app.py` — every `execute()` uses `?` placeholders.
- [ ] No new pip packages installed (`pip freeze` is unchanged from before this step).
