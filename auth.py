"""routes/auth.py - /signup, /login, /logout as a Flask blueprint."""
import re

from flask import Blueprint, flash, redirect, render_template, request, url_for
from flask_login import current_user, login_required, login_user, logout_user

from extensions import db
from models_auth import User, get_password_errors

bp = Blueprint("auth", __name__)

EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


def is_safe_next(target):
    """Only allow redirects to paths inside this site."""
    return bool(target) and target.startswith("/") and not target.startswith("//")


@bp.route("/signup", methods=["GET", "POST"])
def signup():
    if current_user.is_authenticated:
        return redirect(url_for("dashboard"))

    if request.method == "POST":
        name = request.form.get("name", "").strip()
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")
        confirm = request.form.get("confirm_password", "")

        errors = []
        if not name:
            errors.append("Enter your name.")
        if not EMAIL_RE.match(email):
            errors.append("Enter a valid email address.")
        elif User.query.filter_by(email=email).first():
            errors.append("An account with this email already exists. Try logging in.")

        problems = get_password_errors(password)
        if problems:
            errors.append("Password needs " + ", ".join(problems) + ".")
        elif password != confirm:
            errors.append("Passwords do not match.")

        if errors:
            for message in errors:
                flash(message, "danger")
            return render_template("signup.html", form=request.form), 400

        user = User(name=name, email=email)
        user.set_password(password)
        db.session.add(user)
        db.session.commit()

        login_user(user)
        flash(f"Welcome, {user.name}. Your account is ready.", "success")
        return redirect(url_for("dashboard"))

    return render_template("signup.html", form={})


@bp.route("/login", methods=["GET", "POST"])
def login():
    if current_user.is_authenticated:
        return redirect(url_for("dashboard"))

    if request.method == "POST":
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")
        remember = request.form.get("remember") == "on"

        user = User.query.filter_by(email=email).first()
        if user is None or not user.check_password(password):
            flash("Email or password is incorrect.", "danger")
            return render_template("login.html", form=request.form), 401

        login_user(user, remember=remember)
        next_page = request.args.get("next")
        return redirect(next_page if is_safe_next(next_page) else url_for("dashboard"))

    return render_template("login.html", form={})


@bp.route("/logout", methods=["POST"])
@login_required
def logout():
    logout_user()
    flash("You have been logged out.", "info")
    return redirect(url_for("auth.login"))
