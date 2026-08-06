# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project

Spendly is a Flask-based personal expense tracker (Rupee-focused, target audience India). The codebase is being built incrementally in numbered steps (database setup → API → UI), and the current state only reflects the steps completed so far. Future steps will fill in `database/db.py`, add real route handlers (register/login/profile/expenses), and add tests.

## Run

```bash
# Dev server (Flask, debug mode, port 5001)
python app.py

# Virtualenv already exists at ./venv
source venv/bin/activate   # or venv\Scripts\activate on Windows
pip install -r requirements.txt   # if venv is missing
```

Open http://127.0.0.1:5001 — landing page is the root.

## Tests

```bash
pytest                              # all tests
pytest tests/test_xyz.py            # single file
pytest tests/test_xyz.py::test_foo  # single test
```

A `tests/` directory does not exist yet. `pytest` and `pytest-flask` are in `requirements.txt` but no tests have been written.

## Architecture

```
app.py                  # Flask app + all routes (see below)
database/
  __init__.py           # empty
  db.py                 # stub — students implement get_db(), init_db(), seed_db()
templates/
  base.html             # navbar + footer + {% block content %} + {% block scripts %}
  landing.html          # public landing page (hero, features, CTA, video modal)
  login.html / register.html   # auth forms (POST handlers not yet implemented)
  terms.html / privacy.html   # legal pages
static/
  css/style.css         # single stylesheet, all pages
  js/main.js            # placeholder, page-level JS goes here
  landing_page.png      # design mockup referenced by the hero redesign step
```

There is no `models/`, `services/`, or `blueprint/` split — everything lives in `app.py` and templates. Keep this layout until the project deliberately introduces a split.

## Routes in `app.py`

Implemented (render templates only):
- `GET /` → `landing.html`
- `GET /register` → `register.html`
- `GET /login` → `login.html`
- `GET /terms` → `terms.html`
- `GET /privacy` → `privacy.html`

Placeholders returning strings (do not implement unless asked):
- `/logout`, `/profile`, `/expenses/add`, `/expenses/<id>/edit`, `/expenses/<id>/delete`

The login/register forms currently POST to `/login` and `/register` but those handlers are not implemented yet — submitting them returns a 405.

## Frontend conventions

- Templates extend `base.html`. Use `{% block content %}` for body and `{% block scripts %}` for per-page JS (rendered after `main.js`).
- All static assets go through `url_for('static', filename=...)`.
- One stylesheet (`static/css/style.css`). CSS custom properties at the top of the file define the palette — reuse them rather than hardcoding colors.
- Brand wordmark uses `◈`; use `&#8377;` for the rupee symbol (do not use `&rupee;`, which is not a valid HTML entity).
- Vanilla JS only — no frameworks, no build step. Place code in `main.js` or a per-page `{% block scripts %}` block.

## Modal pattern (landing page)

The "See how it works" button opens a YouTube modal in `landing.html`. The pattern is important and is reused elsewhere:

- Trigger: `data-open-modal` attribute on the trigger element.
- Close: `data-close-modal` on the close button and backdrop.
- The iframe's `src` is set to `about:blank` initially; the real URL is in `data-src`. The JS swaps `src` back to `data-src` on open and to `about:blank` on close — this is what stops playback (unmounting the YouTube player is the only reliable way to stop it; `pauseVideo()` postMessage doesn't work cross-browser).
- Body scroll is locked with `document.body.style.overflow = 'hidden'` while open.
- Escape key closes the modal.

## Database stub

`database/db.py` is currently a comment-only file. When the database step is in scope, it should expose:
- `get_db()` — sqlite3 connection with `row_factory = sqlite3.Row` and `PRAGMA foreign_keys = ON`
- `init_db()` — `CREATE TABLE IF NOT EXISTS` for all tables
- `seed_db()` — sample data for development

`expense_tracker.db` is gitignored.

## Concurrency note

`app.py` runs with `debug=True` on port 5001. Don't change the port without checking — other tooling (tests, scripts) may assume it.
