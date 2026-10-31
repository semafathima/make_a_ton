from datetime import date

from flask import Blueprint, flash, redirect, render_template, request, url_for

from extensions import db
from models import Discount
from utils import parse_decimal

bp = Blueprint("discounts", __name__, url_prefix="/discounts")


@bp.route("", methods=["GET", "POST"], strict_slashes=False)
def index():
    if request.method == "POST":
        code = request.form.get("code", "").strip().upper()
        kind = request.form.get("kind")
        value = parse_decimal(request.form.get("value", ""))
        valid_until = request.form.get("valid_until") or None

        if not code or kind not in ("fixed", "percent") or value is None:
            flash("Code, type and a valid value are required.", "danger")
        elif kind == "percent" and value > 100:
            flash("Percentage cannot exceed 100.", "danger")
        elif Discount.query.filter_by(code=code).first():
            flash("That code already exists.", "danger")
        else:
            db.session.add(Discount(
                code=code, kind=kind, value=value,
                valid_until=date.fromisoformat(valid_until) if valid_until else None,
            ))
            db.session.commit()
            flash(f"Discount {code} created.", "success")
        return redirect(url_for("discounts.index"))

    return render_template("discounts.html", discounts=Discount.query.order_by(Discount.id.desc()).all())


@bp.post("/<int:discount_id>/toggle")
def toggle(discount_id):
    d = db.get_or_404(Discount, discount_id)
    d.active = not d.active
    db.session.commit()
    return redirect(url_for("discounts.index"))