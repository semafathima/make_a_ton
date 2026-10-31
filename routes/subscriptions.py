from datetime import datetime
from decimal import Decimal

from flask import Blueprint, flash, redirect, render_template, request, url_for

from extensions import db
from models import Discount, Plan, Quote, SubscriptionOrder

bp = Blueprint("subscriptions", __name__, url_prefix="/subscriptions")


@bp.route("", strict_slashes=False)
def index():
    return render_template(
        "subscriptions.html",
        plans=Plan.query.all(),
        quotes=Quote.query.order_by(Quote.created_at.desc()).all(),
        subscriptions=SubscriptionOrder.query.order_by(SubscriptionOrder.created_at.desc()).all(),
    )


@bp.post("/quotes")
def create_quote():
    customer = request.form.get("customer_name", "").strip()
    plan = db.session.get(Plan, request.form.get("plan_id", type=int) or 0)
    qty = request.form.get("quantity", 1, type=int)
    code = request.form.get("discount_code", "").strip().upper()

    if not customer or plan is None or qty < 1:
        flash("Customer, plan and a quantity of at least 1 are required.", "danger")
        return redirect(url_for("subscriptions.index"))

    subtotal = Decimal(plan.price) * qty
    discount_amount = Decimal("0.00")
    if code:
        discount = Discount.query.filter_by(code=code).first()
        if discount is None or not discount.is_valid():
            flash(f"Discount code '{code}' is invalid, inactive or expired.", "danger")
            return redirect(url_for("subscriptions.index"))
        discount_amount = discount.amount_for(subtotal)

    db.session.add(Quote(
        customer_name=customer,
        customer_email=request.form.get("customer_email", "").strip(),
        plan_id=plan.id, quantity=qty, discount_code=code,
        subtotal=subtotal, discount_amount=discount_amount,
        total=subtotal - discount_amount,
    ))
    db.session.commit()
    flash("Quote created.", "success")
    return redirect(url_for("subscriptions.index"))


@bp.post("/quotes/<int:quote_id>/convert")
def convert_quote(quote_id):
    quote = db.get_or_404(Quote, quote_id)
    if quote.subscription:
        flash("This quote already has a subscription.", "warning")
    else:
        db.session.add(SubscriptionOrder(
            quote_id=quote.id, customer_name=quote.customer_name,
            plan_id=quote.plan_id, total=quote.total, state="Draft",
        ))
        db.session.commit()
        flash("Subscription created in Draft state.", "success")
    return redirect(url_for("subscriptions.index"))


@bp.post("/<int:sub_id>/transition")
def transition(sub_id):
    sub = db.get_or_404(SubscriptionOrder, sub_id)
    target = request.form.get("to")
    # Only the next step in the lifecycle is allowed
    if target != sub.next_state:
        flash(f"Cannot move from {sub.state} to {target}.", "danger")
        return redirect(url_for("subscriptions.index"))

    sub.state = target
    if target == "Active":
        sub.started_at = datetime.utcnow()
    elif target == "Closed":
        sub.closed_at = datetime.utcnow()
    db.session.commit()
    flash(f"Subscription #{sub.id} is now {target}.", "success")
    return redirect(url_for("subscriptions.index"))