# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project

Spendly is a Flask-based personal expense tracker (Rupee-focused, target audience India). The codebase is being built incrementally in numbered steps via specs in `.claude/specs/` (01-database-setup → 02-registration → 03-login-and-logout → 04-profile-info → 05-date-filter-on-profile-page, …). Each step has a matching implementation plan in `.claude/plans/`. The current state reflects only the steps completed so far — don't assume routes/features that aren't mentioned in `app.py` exist.

## Run

```bash
# Dev server (Flask, debug mode, port 5001)
python app.py

# Virtualenv already exists at ./venv
source venv/bin/activate   # or venv\Scripts\activate on Windows
pip install -r requirements.txt   # only if venv is missing
```

Open http://127.0.0.1:5001 — landing page is the root. The DB schema is bootstrapped on app startup (`init_db()` + `seed_db()` in `app.py`).

## Tests

```bash
pytest                              # all tests
pytest tests/test_xyz.py            # single file
pytest tests/test_xyz.py::test_foo  # single test
```

A `tests/` directory does not exist yet. `pytest` and `pytest-flask` are in `requirements.txt`. Tests should use `pytest-flask`'s `client` fixture and a temp DB (never the real `expense_tracker.db`) — see the `test-writer` subagent for the pattern.

## Architecture

```
app.py                  # Flask app + all routes + helpers (see "Routes" below)
database/
  __init__.py           # empty
  db.py                 # get_db(), init_db(), seed_db() — SQLite, row_factory=sqlite3.Row, FK on
templates/
  base.html             # navbar + footer + {% block content %} + {% block scripts %}
  landing.html          # public landing page (hero, features, CTA, video modal)
  login.html / register.html   # auth forms (POST handlers implemented)
  terms.html / privacy.html   # legal pages
  profile.html          # signed-in dashboard (stats, category breakdown, recent transactions)
static/
  css/style.css         # single stylesheet, all pages
  js/main.js            # placeholder, page-level JS goes here
  landing_page.png      # design mockup referenced by the hero redesign step
```

There is no `models/`, `services/`, or `blueprint/` split — everything lives in `app.py` and templates. Keep this layout until the project deliberately introduces a split.

## Database

`database/db.py` is fully implemented, not a stub. Tables:

- `users(id, name, email UNIQUE, password_hash, created_at)` — created via `werkzeug.security.generate_password_hash`.
- `expenses(id, user_id FK→users, amount, category, date YYYY-MM-DD, description, created_at)` — `ON DELETE CASCADE`.

`seed_db()` is idempotent — one demo user (`demo@spendly.com` / `demo123`) and 8 sample expenses. It bails out once the `users` table is non-empty. `expense_tracker.db` is gitignored.

Routes that hit the DB own their connection: `conn = get_db()` … `conn.close()` in a `finally:` block. Don't refactor to a request-scoped teardown without a deliberate design change.

## Routes in `app.py`

Implemented:
- `GET /` → `landing.html` (redirects to `/profile` if logged in)
- `GET|POST /register` → `register.html` (form validation, hash, session, redirect)
- `GET|POST /login` → `login.html` (lookup by email, verify hash, session)
- `GET /logout` → clears session, redirects to `/login`
- `GET /profile` → `profile.html` (requires auth, `?from=&to=` date filter)
- `GET /terms` → `terms.html`
- `GET /privacy` → `privacy.html`

Stubs (return placeholder strings, do not implement unless asked):
- `/expenses/add`, `/expenses/<int:id>/edit`, `/expenses/<int:id>/delete`

## Sessions, auth, and form errors

Session-based auth with two keys: `session["user_id"]` (int) and `session["user_name"]` (str). The private helper `_current_user()` returns `session.get("user_id")` or `None`.

Form-validation errors follow Post/Redirect/Get: `flash(message)` → `redirect(url_for(...))` → the GET branch pulls the first flashed message and re-renders the template with `error=...`. Use the same pattern for new forms.

## Frontend conventions

- Templates extend `base.html`. Use `{% block content %}` for body and `{% block scripts %}` for per-page JS (rendered after `main.js`).
- All static assets go through `url_for('static', filename=...)`.
- One stylesheet (`static/css/style.css`). CSS custom properties at the top of the file define the palette — reuse them rather than hardcoding colors.
- Brand wordmark uses `◈`; use `&#8377;` for the rupee symbol (do not use `&rupee;`, which is not a valid HTML entity).
- Dates: `YYYY-MM-DD` strings (ISO); they sort lexicographically == chronologically, so `BETWEEN ? AND ?` on text columns is correct (used by `/profile` range filter).
- Vanilla JS only — no frameworks, no build step. Place code in `main.js` or a per-page `{% block scripts %}` block.

## Modal pattern (landing page)

The "See how it works" button opens a YouTube modal in `landing.html`. The pattern is important and is reused elsewhere:

- Trigger: `data-open-modal` attribute on the trigger element.
- Close: `data-close-modal` on the close button and backdrop.
- The iframe's `src` is set to `about:blank` initially; the real URL is in `data-src`. The JS swaps `src` back to `data-src` on open and to `about:blank` on close — this is what stops playback (unmounting the YouTube player is the only reliable way to stop it; `pauseVideo()` postMessage doesn't work cross-browser).
- Body scroll is locked with `document.body.style.overflow = 'hidden'` while open.
- Escape key closes the modal.

## Subagents and slash commands

`.claude/` defines project-specific tooling future Claude instances should use instead of improvising:

- **Subagents** (`/general-purpose` with these agent types via the `Agent` tool):
  - `code-reviewer` — read-only review for correctness, security, style, conventions.
  - `test-writer` — writes pytest tests; never runs them.
  - `test-runner` — runs pytest; never edits files.
- **Slash commands** (`.claude/commands/`): `create-spec`, `seed-user`, `seed-expense`, `test-feature`. Use these instead of re-deriving the workflow inline.
- **Skills** (`.claude/skills/`): `frontend-design` for anything visual.

## Incremental workflow

The project grows one step at a time:

1. A spec in `.claude/specs/NN-short-name.md` describes the next step.
2. A plan in `.claude/plans/NN-short-name.md` lays the implementation plan.
3. Implement the step, then write tests for the new behavior.
4. The plan is the source of truth for what the step should do — read it before editing.

When the user asks for "the next step" or to "add a feature," look at the spec and plan files first; both already exist for completed steps and serve as a structural template.

## Concurrency note

`app.py` runs with `debug=True` on port 5001. Don't change the port without checking — other tooling (tests, scripts, subagents) may assume it.
