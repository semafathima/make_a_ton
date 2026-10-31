"""
models_auth.py - User model + strict password rules.
Kept in its own file so it never conflicts with models.py (teammates' file).
"""
import re
from datetime import datetime

from flask_login import UserMixin
from werkzeug.security import check_password_hash, generate_password_hash

from extensions import db, login_manager


def get_password_errors(password):
    """Return a list of problems with the password (empty list = valid).
    Rules: min 8 chars, 1 uppercase, 1 lowercase, 1 special character."""
    password = password or ""
    errors = []
    if len(password) < 8:
        errors.append("at least 8 characters")
    if not re.search(r"[A-Z]", password):
        errors.append("one uppercase letter")
    if not re.search(r"[a-z]", password):
        errors.append("one lowercase letter")
    if not re.search(r"[^A-Za-z0-9]", password):
        errors.append("one special character (e.g. ! @ # $ %)")
    return errors


class User(UserMixin, db.Model):
    __tablename__ = "users"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False, index=True)
    password_hash = db.Column(db.String(255), nullable=False)
    role = db.Column(db.String(20), nullable=False, default="customer")  # customer / admin
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def set_password(self, password):
        """Validate strictly, then store only the hash."""
        errors = get_password_errors(password)
        if errors:
            raise ValueError("Password must contain " + ", ".join(errors) + ".")
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

    def __repr__(self):
        return f"<User {self.email}>"


@login_manager.user_loader
def load_user(user_id):
    return db.session.get(User, int(user_id))
