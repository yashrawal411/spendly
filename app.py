import os
import re
import secrets
import sqlite3
from datetime import date, datetime

from flask import (
    Flask, render_template, request, redirect, session, flash,
    url_for, get_flashed_messages, abort,
)

from werkzeug.security import generate_password_hash, check_password_hash

from database.db import get_db, init_db, seed_db

app = Flask(__name__)

# Secret key: REQUIRE an env var in production so sessions survive restarts.
# A fresh random key per process silently logs every user out on each
# deploy/worker-recycle, which is hard to debug. Local dev still works
# without setup (FLASK_ENV=development gets a per-run random key).
_secret_key = os.environ.get("SECRET_KEY")
if not _secret_key:
    if os.environ.get("FLASK_ENV") == "development":
        _secret_key = secrets.token_hex(32)  # OK for local dev only
    else:
        raise RuntimeError(
            "SECRET_KEY is not set. Set it in your environment "
            "(e.g. `railway variables set SECRET_KEY=...`) — sessions "
            "won't survive restarts without it."
        )
app.secret_key = _secret_key

# Loose email-format check; HTML5 type="email" handles the user-facing nudge.
EMAIL_RE = re.compile(r"[^@\s]+@[^@\s]+\.[^@\s]+")

# Categories the user can pick when adding or editing an expense. Single
# source of truth — both the form's <select> and the validator share this.
EXPENSE_CATEGORIES = ("Food", "Transport", "Shopping", "Bills",
                      "Entertainment", "Health", "Other")


# ------------------------------------------------------------------ #
# Database bootstrap — runs once on app startup                      #
# ------------------------------------------------------------------ #
with app.app_context():
    init_db()
    seed_db()


# ------------------------------------------------------------------ #
# Routes                                                              #
# ------------------------------------------------------------------ #

@app.route("/")
def landing():
    if _current_user():
        return redirect("/profile")
    return render_template("landing.html")


def _current_user():
    """Return the logged-in user's id, or None."""
    return session.get("user_id")


def _validate_registration(name, email, password, confirm):
    """Return None on success or a user-facing error string on failure."""
    if not (name and email and password and confirm):
        return "All fields are required."
    if len(name.strip()) < 2:
        return "Please enter your full name."
    if not EMAIL_RE.match(email):
        return "Please enter a valid email address."
    if len(password) < 8:
        return "Password must be at least 8 characters."
    if password != confirm:
        return "Passwords do not match."
    return None


def _validate_expense_form(amount_raw, category_raw, date_raw, description_raw):
    """Return None on success or a user-facing error string on failure.

    Used by both /expenses/add and /expenses/<id>/edit. The description is
    optional and length-capped by the input's maxlength + a slice in the
    handler — the helper does not enforce it.
    """
    if not amount_raw:
        return "Please enter a valid amount."
    try:
        amount = float(amount_raw)
    except ValueError:
        return "Please enter a valid amount."
    if amount <= 0 or amount > 1_00_00_000:
        return "Please enter a valid amount."

    if category_raw not in EXPENSE_CATEGORIES:
        return "Please pick a category."

    try:
        datetime.strptime(date_raw, "%Y-%m-%d")
    except (ValueError, TypeError):
        return "Please enter a valid date (YYYY-MM-DD)."

    return None


@app.route("/register", methods=["GET", "POST"])
def register():
    if _current_user():
        return redirect("/profile")
    if request.method == "POST":
        name = (request.form.get("name") or "").strip()
        email = (request.form.get("email") or "").strip().lower()
        password = request.form.get("password") or ""
        confirm = request.form.get("confirm_password") or ""

        error = _validate_registration(name, email, password, confirm)
        if error:
            # Post/Redirect/Get: refresh after a failed POST becomes a clean GET.
            flash(error)
            return redirect(url_for("register"))

        conn = get_db()
        try:
            cur = conn.cursor()
            try:
                cur.execute(
                    "INSERT INTO users (name, email, password_hash) VALUES (?, ?, ?)",
                    (name, email, generate_password_hash(password)),
                )
                conn.commit()
                new_id = cur.lastrowid
            except sqlite3.IntegrityError:
                conn.rollback()
                flash("An account with that email already exists.")
                return redirect(url_for("register"))
        finally:
            conn.close()

        session["user_id"] = new_id
        session["user_name"] = name
        return redirect("/profile")

    # GET: pull any flashed error from a previous POST and surface it on the form.
    flashed = get_flashed_messages()
    return render_template("register.html", error=flashed[0] if flashed else None)


@app.route("/login", methods=["GET", "POST"])
def login():
    if _current_user():
        return redirect("/profile")
    if request.method == "POST":
        email = (request.form.get("email") or "").strip().lower()
        password = request.form.get("password") or ""

        if not email or not password:
            flash("Invalid email or password.")
            return redirect(url_for("login"))

        conn = get_db()
        try:
            cur = conn.cursor()
            row = cur.execute(
                "SELECT id, name, password_hash FROM users WHERE email = ?",
                (email,),
            ).fetchone()
        finally:
            conn.close()

        if row is None or not check_password_hash(row["password_hash"], password):
            flash("Invalid email or password.")
            return redirect(url_for("login"))

        session["user_id"] = row["id"]
        session["user_name"] = row["name"]
        return redirect("/profile")

    flashed = get_flashed_messages()
    return render_template("login.html", error=flashed[0] if flashed else None)


@app.route("/terms")
def terms():
    return render_template("terms.html")


@app.route("/privacy")
def privacy():
    return render_template("privacy.html")


# ------------------------------------------------------------------ #
# Placeholder routes — students will implement these                  #
# ------------------------------------------------------------------ #

@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("login"))


@app.route("/profile")
def profile():
    user_id = _current_user()
    if user_id is None:
        flash("Please sign in to view your profile.")
        return redirect(url_for("login"))

    conn = get_db()
    try:
        cur = conn.cursor()
        user_row = cur.execute(
            "SELECT id, name, email, created_at FROM users WHERE id = ?",
            (user_id,),
        ).fetchone()
        # All-time aggregates. The date filter has moved to /expenses
        # (step 07); the profile page is now a fixed all-time dashboard.
        stats = cur.execute(
            "SELECT COUNT(*) AS n, COALESCE(SUM(amount), 0) AS total "
            "FROM expenses WHERE user_id = ?",
            (user_id,),
        ).fetchone()

        # Top category (None when user has zero expenses).
        top_category_row = cur.execute(
            "SELECT category, SUM(amount) AS total "
            "FROM expenses WHERE user_id = ? "
            "GROUP BY category "
            "ORDER BY total DESC "
            "LIMIT 1",
            (user_id,),
        ).fetchone()

        # Recent 5 transactions (0–5 rows), newest first.
        recent_rows = cur.execute(
            "SELECT id, date, category, description, amount "
            "FROM expenses WHERE user_id = ? "
            "ORDER BY date DESC, id DESC "
            "LIMIT 5",
            (user_id,),
        ).fetchall()

        # Category totals, descending (empty list if no expenses).
        category_rows = cur.execute(
            "SELECT category, SUM(amount) AS total "
            "FROM expenses WHERE user_id = ? "
            "GROUP BY category "
            "ORDER BY total DESC",
            (user_id,),
        ).fetchall()
    finally:
        conn.close()

    if user_row is None:
        session.clear()
        flash("Your account could not be found. Please sign in again.")
        return redirect(url_for("login"))

    name = user_row["name"] or ""
    avatar = name.strip()[0].upper() if name.strip() else "?"
    created_at = user_row["created_at"]
    member_since = created_at[:10] if created_at else "Unknown"

    top_category = top_category_row["category"] if top_category_row else None
    top_category_amount = top_category_row["total"] if top_category_row else 0

    grand_total = sum(row["total"] for row in category_rows)
    category_totals = [
        {
            "category": row["category"],
            "total": row["total"],
            "percentage": (row["total"] / grand_total * 100) if grand_total else 0,
        }
        for row in category_rows
    ]

    recent_transactions = [
        {
            "id": row["id"],
            "date_display": (row["date"] or "")[:10],
            "category": row["category"],
            "description": row["description"] or "",
            "amount": row["amount"],
        }
        for row in recent_rows
    ]

    return render_template(
        "profile.html",
        name=name,
        email=user_row["email"],
        member_since=member_since,
        avatar=avatar,
        expense_count=stats["n"],
        total_spent=stats["total"],
        top_category=top_category,
        top_category_amount=top_category_amount,
        recent_transactions=recent_transactions,
        category_totals=category_totals,
    )


# ------------------------------------------------------------------ #
# Expenses management (step 07)                                       #
# ------------------------------------------------------------------ #

@app.route("/expenses", methods=["GET"])
def expenses():
    user_id = _current_user()
    if user_id is None:
        flash("Please sign in to manage your expenses.")
        return redirect(url_for("login"))

    # --- Date-range filter (same contract as step 05) -----------------
    filter_from_raw = (request.args.get("from") or "").strip()
    filter_to_raw = (request.args.get("to") or "").strip()
    DATE_FMT = "%Y-%m-%d"
    DEFAULT_FROM = "0000-01-01"
    DEFAULT_TO = "9999-12-31"

    try:
        if filter_from_raw:
            datetime.strptime(filter_from_raw, DATE_FMT)
        if filter_to_raw:
            datetime.strptime(filter_to_raw, DATE_FMT)
    except ValueError:
        flash("Please enter valid dates (YYYY-MM-DD).")
        return redirect(url_for("expenses"))

    filter_from = filter_from_raw or DEFAULT_FROM
    filter_to = filter_to_raw or DEFAULT_TO

    if filter_from > filter_to:  # string compare works on YYYY-MM-DD
        flash("Please enter valid dates (YYYY-MM-DD).")
        return redirect(url_for("expenses"))

    # Inline edit target (?edit=<id>). None means "no row in edit mode".
    edit_id_raw = (request.args.get("edit") or "").strip()
    edit_id = int(edit_id_raw) if edit_id_raw.isdigit() else None

    # Pagination — 10 rows per page. ?page=1 is the first page.
    PAGE_SIZE = 10
    page_raw = (request.args.get("page") or "").strip()
    page = int(page_raw) if page_raw.isdigit() and int(page_raw) >= 1 else 1
    offset = (page - 1) * PAGE_SIZE

    conn = get_db()
    try:
        cur = conn.cursor()

        user_row = cur.execute(
            "SELECT id, name FROM users WHERE id = ?", (user_id,)
        ).fetchone()
        if user_row is None:
            session.clear()
            flash("Your account could not be found. Please sign in again.")
            return redirect(url_for("login"))

        # Top category for the filtered subset.
        top_category_row = cur.execute(
            "SELECT category, SUM(amount) AS total "
            "FROM expenses WHERE user_id = ? AND date BETWEEN ? AND ? "
            "GROUP BY category "
            "ORDER BY total DESC "
            "LIMIT 1",
            (user_id, filter_from, filter_to),
        ).fetchone()

        # Total count for the filtered subset (drives pagination controls).
        total_count_row = cur.execute(
            "SELECT COUNT(*) AS n FROM expenses "
            "WHERE user_id = ? AND date BETWEEN ? AND ?",
            (user_id, filter_from, filter_to),
        ).fetchone()
        total_count = total_count_row["n"]

        # Page slice: 10 rows at a time, newest first.
        rows = cur.execute(
            "SELECT id, date, category, description, amount "
            "FROM expenses WHERE user_id = ? AND date BETWEEN ? AND ? "
            "ORDER BY date DESC, id DESC "
            "LIMIT ? OFFSET ?",
            (user_id, filter_from, filter_to, PAGE_SIZE, offset),
        ).fetchall()

        # If we're editing, fetch the row (ownership-checked). A row that
        # exists but belongs to another user, or doesn't exist at all,
        # both return None — caller responds with 404 (no info leak).
        edit_row = None
        if edit_id is not None:
            edit_row = cur.execute(
                "SELECT id, amount, category, date, description "
                "FROM expenses WHERE id = ? AND user_id = ?",
                (edit_id, user_id),
            ).fetchone()
            if edit_row is None:
                abort(404)
    finally:
        conn.close()

    # --- Form re-population (URL query string on validation failure) ---
    form_amount = (request.args.get("amount") or "").strip()
    form_category = (request.args.get("category") or "").strip() or "Other"
    form_date = (request.args.get("date") or "").strip() or date.today().isoformat()
    form_description = (request.args.get("description") or "").strip()

    # --- Preset URLs for the filter chips (same pattern as step 05) ----
    today = date.today()
    this_month_from = today.replace(day=1).isoformat()  # YYYY-MM-01
    this_month_to = today.isoformat()                   # YYYY-MM-DD
    this_month_url = f"/expenses?from={this_month_from}&to={this_month_to}"
    all_time_url = "/expenses"
    is_all_time = filter_from == DEFAULT_FROM and filter_to == DEFAULT_TO
    is_this_month = filter_from == this_month_from and filter_to == this_month_to

    expenses_list = [
        {
            "id": r["id"],
            "date_display": (r["date"] or "")[:10],
            "category": r["category"],
            "description": r["description"] or "",
            "amount": r["amount"],
        }
        for r in rows
    ]

    top_category = top_category_row["category"] if top_category_row else None
    top_category_amount = top_category_row["total"] if top_category_row else 0

    # --- Pagination metadata ------------------------------------------
    import math
    total_pages = max(1, math.ceil(total_count / PAGE_SIZE))
    # Clamp the page number: a stale ?page=9999 should land on the last page
    # rather than rendering an empty table.
    if page > total_pages:
        clamp_args = {"page": total_pages}
        if filter_from != DEFAULT_FROM:
            clamp_args["from"] = filter_from
        if filter_to != DEFAULT_TO:
            clamp_args["to"] = filter_to
        return redirect(url_for("expenses", **clamp_args))

    def _page_url(p):
        # Build a /expenses?page=N URL that also preserves from/to when set.
        args = {"page": p}
        if filter_from != DEFAULT_FROM:
            args["from"] = filter_from
        if filter_to != DEFAULT_TO:
            args["to"] = filter_to
        return url_for("expenses", **args)

    page_from = offset + 1 if total_count else 0
    page_to = min(offset + PAGE_SIZE, total_count)
    has_prev = page > 1
    has_next = page < total_pages

    return render_template(
        "expenses.html",
        name=user_row["name"],
        expenses=expenses_list,
        top_category=top_category,
        top_category_amount=top_category_amount,
        filter_from=filter_from,
        filter_to=filter_to,
        this_month_url=this_month_url,
        all_time_url=all_time_url,
        is_all_time=is_all_time,
        is_this_month=is_this_month,
        edit_row=edit_row,
        edit_id=edit_id,
        categories=EXPENSE_CATEGORIES,
        form_amount=form_amount,
        form_category=form_category,
        form_date=form_date,
        form_description=form_description,
        page=page,
        total_pages=total_pages,
        total_count=total_count,
        page_from=page_from,
        page_to=page_to,
        has_prev=has_prev,
        has_next=has_next,
        prev_url=_page_url(page - 1) if has_prev else None,
        next_url=_page_url(page + 1) if has_next else None,
    )


@app.route("/expenses/add", methods=["POST"])
def add_expense():
    user_id = _current_user()
    if user_id is None:
        flash("Please sign in to add an expense.")
        return redirect(url_for("login"))

    amount_raw = (request.form.get("amount") or "").strip()
    category_raw = (request.form.get("category") or "").strip()
    date_raw = (request.form.get("date") or "").strip()
    description_raw = (request.form.get("description") or "").strip()

    error = _validate_expense_form(amount_raw, category_raw, date_raw, description_raw)
    if error:
        # Round-trip typed values in the URL so the GET re-renders the form
        # with the user's input still in place.
        flash(error)
        return redirect(url_for("expenses", amount=amount_raw,
                                category=category_raw, date=date_raw,
                                description=description_raw))

    amount = float(amount_raw)
    description = description_raw[:200]

    conn = get_db()
    try:
        cur = conn.cursor()
        cur.execute(
            "INSERT INTO expenses (user_id, amount, category, date, description) "
            "VALUES (?, ?, ?, ?, ?)",
            (user_id, amount, category_raw, date_raw, description),
        )
        conn.commit()
    except sqlite3.IntegrityError:
        conn.rollback()
        flash("Could not save your expense. Please try again.")
        return redirect(url_for("expenses"))
    finally:
        conn.close()

    flash("Expense added.", "success")
    return redirect(url_for("expenses"))


@app.route("/expenses/<int:id>/edit", methods=["POST"])
def edit_expense(id):
    user_id = _current_user()
    if user_id is None:
        flash("Please sign in to edit an expense.")
        return redirect(url_for("login"))

    amount_raw = (request.form.get("amount") or "").strip()
    category_raw = (request.form.get("category") or "").strip()
    date_raw = (request.form.get("date") or "").strip()
    description_raw = (request.form.get("description") or "").strip()

    error = _validate_expense_form(amount_raw, category_raw, date_raw, description_raw)
    if error:
        flash(error)
        return redirect(url_for("expenses", edit=id,
                                amount=amount_raw, category=category_raw,
                                date=date_raw, description=description_raw))

    amount = float(amount_raw)
    description = description_raw[:200]

    conn = get_db()
    try:
        cur = conn.cursor()
        cur.execute(
            "UPDATE expenses SET amount = ?, category = ?, date = ?, description = ? "
            "WHERE id = ? AND user_id = ?",
            (amount, category_raw, date_raw, description, id, user_id),
        )
        conn.commit()
        if cur.rowcount == 0:
            # Row didn't exist or wasn't ours — 404 (no information leak).
            abort(404)
    finally:
        conn.close()

    flash("Expense updated.", "success")
    return redirect(url_for("expenses"))


@app.route("/expenses/<int:id>/delete", methods=["POST"])
def delete_expense(id):
    user_id = _current_user()
    if user_id is None:
        flash("Please sign in to delete an expense.")
        return redirect(url_for("login"))

    conn = get_db()
    try:
        cur = conn.cursor()
        cur.execute(
            "DELETE FROM expenses WHERE id = ? AND user_id = ?",
            (id, user_id),
        )
        conn.commit()
        if cur.rowcount == 0:
            abort(404)
    finally:
        conn.close()

    flash("Expense deleted.", "success")
    return redirect(url_for("expenses"))


if __name__ == "__main__":
    # Local dev only — Railway runs gunicorn via the Procfile.
    port = int(os.environ.get("PORT", "5001"))
    app.run(host="0.0.0.0", port=port, debug=False)
