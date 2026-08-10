import re
import sqlite3

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

    conn = get_db()
    try:
        cur = conn.cursor()
        user_row = cur.execute(
            "SELECT id, name, email, created_at FROM users WHERE id = ?",
            (user_id,),
        ).fetchone()
        stats = cur.execute(
            "SELECT COUNT(*) AS n, COALESCE(SUM(amount), 0) AS total "
            "FROM expenses WHERE user_id = ?",
            (user_id,),
        ).fetchone()
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

    return render_template(
        "profile.html",
        name=name,
        email=user_row["email"],
        member_since=member_since,
        avatar=avatar,
        expense_count=stats["n"],
        expense_total=stats["total"],
    )


@app.route("/expenses/add")
def add_expense():
    return "Add expense — coming in Step 7"


@app.route("/expenses/<int:id>/edit")
def edit_expense(id):
    return "Edit expense — coming in Step 8"


@app.route("/expenses/<int:id>/delete")
def delete_expense(id):
    return "Delete expense — coming in Step 9"


if __name__ == "__main__":
    app.run(debug=True, port=5001)
