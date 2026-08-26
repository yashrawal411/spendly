import re
import sqlite3
from datetime import date, datetime

from flask import (
    Flask, render_template, request, redirect, session, flash,
    url_for, get_flashed_messages,
)

from werkzeug.security import generate_password_hash, check_password_hash

from database.db import get_db, init_db, seed_db

app = Flask(__name__)

# Dev-only — in production this should come from an env var.
app.secret_key = "dev-only-change-me"

# Loose email-format check; HTML5 type="email" handles the user-facing nudge.
EMAIL_RE = re.compile(r"[^@\s]+@[^@\s]+\.[^@\s]+")

# Categories the user can pick when adding an expense. Single source of truth
# for both the standalone form and the profile-page quick-add card.
EXPENSE_CATEGORIES = (
    "Food", "Transport", "Shopping", "Bills",
    "Entertainment", "Health", "Other",
)


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

    # --- Date-range filter (step 05) --------------------------------------
    # Read & validate ?from=YYYY-MM-DD&to=YYYY-MM-DD. Empty / missing values
    # fall back to "all time" wide bounds. Inclusive on both ends (BETWEEN).
    # NOTE: validation runs *inside* the authenticated branch to keep the
    # not-logged-in / stale-session flows untouched.
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
        return redirect(url_for("profile"))

    filter_from = filter_from_raw or DEFAULT_FROM
    filter_to = filter_to_raw or DEFAULT_TO

    if filter_from > filter_to:  # string compare works on YYYY-MM-DD
        flash("Please enter valid dates (YYYY-MM-DD).")
        return redirect(url_for("profile"))

    conn = get_db()
    try:
        cur = conn.cursor()
        user_row = cur.execute(
            "SELECT id, name, email, created_at FROM users WHERE id = ?",
            (user_id,),
        ).fetchone()
        # YYYY-MM-DD strings sort lexicographically == chronologically, so
        # BETWEEN ? AND ? is correct (and inclusive on both ends).
        stats = cur.execute(
            "SELECT COUNT(*) AS n, COALESCE(SUM(amount), 0) AS total "
            "FROM expenses WHERE user_id = ? AND date BETWEEN ? AND ?",
            (user_id, filter_from, filter_to),
        ).fetchone()

        # Top category (None when user has zero expenses in the range).
        top_category_row = cur.execute(
            "SELECT category, SUM(amount) AS total "
            "FROM expenses WHERE user_id = ? AND date BETWEEN ? AND ? "
            "GROUP BY category "
            "ORDER BY total DESC "
            "LIMIT 1",
            (user_id, filter_from, filter_to),
        ).fetchone()

        # Recent 5 transactions (0–5 rows) within the range.
        recent_rows = cur.execute(
            "SELECT id, date, category, description, amount "
            "FROM expenses WHERE user_id = ? AND date BETWEEN ? AND ? "
            "ORDER BY date DESC, id DESC "
            "LIMIT 5",
            (user_id, filter_from, filter_to),
        ).fetchall()

        # Category totals, descending (empty list if no expenses in range).
        category_rows = cur.execute(
            "SELECT category, SUM(amount) AS total "
            "FROM expenses WHERE user_id = ? AND date BETWEEN ? AND ? "
            "GROUP BY category "
            "ORDER BY total DESC",
            (user_id, filter_from, filter_to),
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

    # Pre-formatted display values for the template.
    total_spent = stats["total"]
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

    # --- Filter UI state (step 05) ----------------------------------------
    today = date.today()
    this_month_from = today.replace(day=1).isoformat()  # YYYY-MM-01
    this_month_to = today.isoformat()                   # YYYY-MM-DD
    this_month_url = f"/profile?from={this_month_from}&to={this_month_to}"
    all_time_url = "/profile"
    is_all_time = filter_from == DEFAULT_FROM and filter_to == DEFAULT_TO
    is_this_month = (
        filter_from == this_month_from and filter_to == this_month_to
    )

    return render_template(
        "profile.html",
        name=name,
        email=user_row["email"],
        member_since=member_since,
        avatar=avatar,
        expense_count=stats["n"],
        expense_total=stats["total"],
        total_spent=total_spent,
        top_category=top_category,
        top_category_amount=top_category_amount,
        recent_transactions=recent_transactions,
        category_totals=category_totals,
        filter_from=filter_from,
        filter_to=filter_to,
        this_month_url=this_month_url,
        all_time_url=all_time_url,
        is_all_time=is_all_time,
        is_this_month=is_this_month,
        EXPENSE_CATEGORIES=EXPENSE_CATEGORIES,
        today=date.today().isoformat(),
    )


def _safe_next_url(raw_next):
    """Return raw_next only if it points at /profile; else fall back to /profile.

    Rejects absolute URLs, scheme-relative URLs (//evil.example), and anything
    not starting with a single leading slash followed by 'profile'. The open-
    redirect defence is deliberately strict — we'd rather send the user back
    to /profile than to an attacker-controlled URL.
    """
    if not raw_next:
        return "/profile"
    if not raw_next.startswith("/profile"):
        return "/profile"
    return raw_next


def _validate_expense_form(amount_raw, category_raw, date_raw, description_raw):
    """Return None on success or a user-facing error string on failure.

    Mirrors the shape of _validate_registration: first error wins, plain
    strings, no exceptions leak to the caller.
    """
    if not amount_raw:
        return "Enter a valid amount greater than zero."
    try:
        amount = float(amount_raw)
    except ValueError:
        return "Enter a valid amount greater than zero."
    if amount <= 0:
        return "Enter a valid amount greater than zero."
    # 12 digits before the decimal is a sanity cap (prevents 1e308 shenanigans).
    if len(amount_raw.split(".")[0]) > 12:
        return "Enter a valid amount greater than zero."

    if category_raw not in EXPENSE_CATEGORIES:
        return "Choose a category."

    try:
        datetime.strptime(date_raw, "%Y-%m-%d")
    except (ValueError, TypeError):
        return "Enter a valid date (YYYY-MM-DD)."

    return None


@app.route("/expenses/add", methods=["GET", "POST"])
def add_expense():
    user_id = _current_user()
    if user_id is None:
        flash("Please sign in to add an expense.")
        return redirect(url_for("login"))

    if request.method == "POST":
        amount_raw = (request.form.get("amount") or "").strip()
        category_raw = (request.form.get("category") or "").strip()
        date_raw = (request.form.get("date") or "").strip()
        description_raw = (request.form.get("description") or "").strip()
        next_url = _safe_next_url(request.form.get("next"))

        error = _validate_expense_form(
            amount_raw, category_raw, date_raw, description_raw,
        )
        if error:
            # PRG: round-trip the form values back through the query string so
            # a validation failure preserves what the user typed. The GET branch
            # reads them back via request.args.
            flash(error)
            return redirect(url_for("add_expense", **{
                "amount": amount_raw,
                "category": category_raw,
                "date": date_raw,
                "description": description_raw,
                "next": next_url,
            }))

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
            return redirect(url_for("add_expense", next=next_url))
        finally:
            conn.close()

        return redirect(next_url)

    # GET: pull any flashed error from a previous POST; echo the query-string
    # form values back so a round-trip after a validation failure preserves
    # what the user typed.
    flashed = get_flashed_messages()
    today = date.today().isoformat()
    next_url = _safe_next_url(request.args.get("next"))
    return render_template(
        "add_expense.html",
        error=flashed[0] if flashed else None,
        today=today,
        categories=EXPENSE_CATEGORIES,
        selected_category=request.args.get("category") or "Other",
        amount=request.args.get("amount") or "",
        date=request.args.get("date") or today,
        description=request.args.get("description") or "",
        next_url=next_url,
    )


@app.route("/expenses/<int:id>/edit")
def edit_expense(id):
    return "Edit expense — coming in Step 8"


@app.route("/expenses/<int:id>/delete")
def delete_expense(id):
    return "Delete expense — coming in Step 9"


if __name__ == "__main__":
    app.run(debug=True, port=5001)
