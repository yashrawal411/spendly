# Spec: Registration

## Overview

The Registration step wires up the existing `/register` page so a new visitor can create a Spendly account. Until now `GET /register` only renders `templates/register.html`; submitting the form POSTs to `/register` and gets a 405 because no handler exists. This step adds the POST handler, hashes the password with werkzeug, persists the user with `INSERT INTO users`, and logs the new user in immediately by storing their `user_id` in `session`. After this step, signing up a fresh user lands them logged in on the home/dashboard area, and duplicate emails are rejected cleanly.

## Depends on

- Step 01 — Database setup (`users` table with `UNIQUE` on `email`, `password_hash`, `created_at`; `get_db()` helper).

## Routes

- `POST /register` — Validate `name`, `email`, `password`, and `confirm_password` from the form. On success: hash the password, insert into `users`, store `user_id` in `session`, redirect to `/profile`. On failure (missing field, password mismatch, duplicate email, malformed email): re-render `register.html` with an error message. Access level: **public**.
- `GET /register` — Already implemented (renders the form). No behaviour change.

## Database changes

No database changes. The `users` table created in Step 01 (`database/db.py:43`) is sufficient:

- `name TEXT NOT NULL`
- `email TEXT NOT NULL UNIQUE`
- `password_hash TEXT NOT NULL`
- `created_at TEXT NOT NULL DEFAULT (datetime('now'))`

The UNIQUE constraint on `email` is what makes duplicate-email detection free at the DB layer.

## Templates

- **Modify:** `templates/register.html` — Render any flashed error message (`{{ error }}`) above the form. Keep all field names (`name`, `email`, `password`, `confirm_password`) so the existing markup keeps working.
- **Modify:** `templates/base.html` — Only if the existing base template does not already include the navbar login/logout links that need to reflect a logged-in state; minimum change is to ensure flash messages render if not already wired up.

## Files to change

- `app.py` — Replace the `register()` view with one that handles both `GET` (render form) and `POST` (validate, insert, log in, redirect). Add a `SECRET_KEY` so `session` works. Add a small `register_user(name, email, password)` helper or inline the logic — whichever is cleaner.
- `templates/register.html` — Add error display for flashed messages.

## Files to create

- None.

## New dependencies

No new dependencies. `werkzeug.security.generate_password_hash` and `werkzeug.security.check_password_hash` are already in `requirements.txt`. `sqlite3` is in the standard library.

## Rules for implementation

- No SQLAlchemy or ORMs. Use `sqlite3` directly via `database.db.get_db()`.
- Parameterised queries only — every `INSERT`/`SELECT` must use `?` placeholders. No f-strings or `%` formatting inside SQL.
- Passwords must be hashed with `werkzeug.security.generate_password_hash` before being stored. Never write the plaintext password to disk.
- Use CSS variables from `static/css/style.css` for any new colours. Do not hardcode hex values in templates or inline styles.
- All templates extend `base.html` and use the existing `{% block content %}` block. Per-page JS goes in `{% block scripts %}`.
- Set a non-empty `app.secret_key` so `flask.session` works. Use a config value or a constant in `app.py`; do not commit a real production secret.
- On `IntegrityError` from the UNIQUE(email) constraint, show a friendly "email already registered" message rather than a 500.
- Email validation: a simple regex (e.g. `[^@\s]+@[^@\s]+\.[^@\s]+`) is enough at this stage. Do not pull in a new validation library.
- Password minimum length: 8 characters. Confirm-password field must match.
- After successful registration, store `session['user_id'] = new_id` and `session['user_name'] = name`, then `redirect('/profile')` (the Profile page is still a placeholder string in Step 01 — that's fine, this step just needs the redirect to succeed with a 302).
- `app.py` must continue to call `init_db()` and `seed_db()` on startup as it does today — do not regress the bootstrap.

## Definition of done

- [ ] Submitting `POST /register` with `name`, `email`, matching `password` / `confirm_password` (each ≥ 8 chars) creates a row in `users` and redirects (302) to `/profile`.
- [ ] The newly inserted row's `password_hash` is a werkzeug hash (starts with `pbkdf2:` or `scrypt:`), not plaintext.
- [ ] Submitting the same email twice shows an error on the form and does NOT create a second row. `SELECT COUNT(*) FROM users WHERE email = ?` returns 1.
- [ ] Submitting `password` ≠ `confirm_password` shows an error and inserts nothing.
- [ ] Missing `name`, `email`, or `password` shows an error and inserts nothing.
- [ ] After registration, `flask.session['user_id']` matches the new user's `id`.
- [ ] `app.run(debug=True, port=5001)` still starts cleanly. Landing at `http://127.0.0.1:5001/register` and submitting a valid form results in a 302 to `/profile`.
- [ ] No raw SQL string formatting anywhere in `app.py` — every `execute()` uses `?` placeholders.
- [ ] No new pip packages installed (`pip freeze` is unchanged from before this step).
