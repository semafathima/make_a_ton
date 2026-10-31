from flask import Blueprint, flash, redirect, render_template, request, url_for

from extensions import db
from models import Plan, Product
from utils import parse_decimal

bp = Blueprint("products", __name__, url_prefix="/products")


@bp.route("", methods=["GET", "POST"], strict_slashes=False)
def index():
    if request.method == "POST":
        name = request.form.get("name", "").strip()
        if not name:
            flash("Product name is required.", "danger")
            return redirect(url_for("products.index"))

        product = Product(name=name, description=request.form.get("description", "").strip())
        db.session.add(product)

        # Optional quick-add of default Monthly / Yearly plans
        for period in ("monthly", "yearly"):
            raw = request.form.get(f"{period}_price", "").strip()
            if raw:
                price = parse_decimal(raw)
                if price is None:
                    db.session.rollback()
                    flash(f"Invalid {period} price.", "danger")
                    return redirect(url_for("products.index"))
                product.plans.append(Plan(name="Standard", billing_period=period, price=price))

        db.session.commit()
        flash(f"Product '{name}' added.", "success")
        return redirect(url_for("products.index"))

    products = Product.query.order_by(Product.created_at.desc()).all()
    return render_template("products.html", products=products)


@bp.post("/<int:product_id>/plans")
def add_plan(product_id):
    product = db.get_or_404(Product, product_id)
    name = request.form.get("name", "").strip()
    period = request.form.get("billing_period")
    price = parse_decimal(request.form.get("price", ""))

    if not name or period not in ("monthly", "yearly") or price is None:
        flash("Variant name, billing period and a valid price are required.", "danger")
    else:
        db.session.add(Plan(product_id=product.id, name=name, billing_period=period, price=price))
        db.session.commit()
        flash(f"Plan '{name}' ({period}) added to {product.name}.", "success")
    return redirect(url_for("products.index"))