from datetime import datetime, date
from decimal import Decimal

from extensions import db


class Product(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), nullable=False)
    description = db.Column(db.Text, default="")
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    plans = db.relationship("Plan", backref="product", cascade="all, delete-orphan")


class Plan(db.Model):
    """A variant of a product with its own price and billing period."""
    id = db.Column(db.Integer, primary_key=True)
    product_id = db.Column(db.Integer, db.ForeignKey("product.id"), nullable=False)
    name = db.Column(db.String(80), nullable=False)            # e.g. "Basic", "Pro"
    billing_period = db.Column(db.String(10), nullable=False)  # "monthly" | "yearly"
    price = db.Column(db.Numeric(10, 2), nullable=False)

    @property
    def label(self):
        return f"{self.product.name} - {self.name} ({self.billing_period})"


class Discount(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    code = db.Column(db.String(40), unique=True, nullable=False)
    kind = db.Column(db.String(10), nullable=False)  # "fixed" | "percent"
    value = db.Column(db.Numeric(10, 2), nullable=False)
    active = db.Column(db.Boolean, default=True)
    valid_until = db.Column(db.Date, nullable=True)

    def is_valid(self):
        if not self.active:
            return False
        return self.valid_until is None or self.valid_until >= date.today()

    def amount_for(self, subtotal):
        subtotal = Decimal(subtotal)
        if self.kind == "percent":
            amount = subtotal * Decimal(self.value) / Decimal(100)
        else:
            amount = Decimal(self.value)
        return min(amount, subtotal).quantize(Decimal("0.01"))


class Quote(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    customer_name = db.Column(db.String(120), nullable=False)
    customer_email = db.Column(db.String(120), default="")
    plan_id = db.Column(db.Integer, db.ForeignKey("plan.id"), nullable=False)
    quantity = db.Column(db.Integer, default=1)
    discount_code = db.Column(db.String(40), default="")
    subtotal = db.Column(db.Numeric(10, 2), nullable=False)
    discount_amount = db.Column(db.Numeric(10, 2), default=0)
    total = db.Column(db.Numeric(10, 2), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    plan = db.relationship("Plan")
    subscription = db.relationship("SubscriptionOrder", backref="quote", uselist=False)


class SubscriptionOrder(db.Model):
    """Quote-to-subscription lifecycle. (Named differently from the billing
    module's Subscription model to avoid a clash.)"""
    __tablename__ = "subscription_order"
    STATES = ["Draft", "Quotation", "Confirmed", "Active", "Closed"]

    id = db.Column(db.Integer, primary_key=True)
    quote_id = db.Column(db.Integer, db.ForeignKey("quote.id"), unique=True)
    customer_name = db.Column(db.String(120), nullable=False)
    plan_id = db.Column(db.Integer, db.ForeignKey("plan.id"), nullable=False)
    total = db.Column(db.Numeric(10, 2), nullable=False)
    state = db.Column(db.String(20), default="Draft", nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    started_at = db.Column(db.DateTime)
    closed_at = db.Column(db.DateTime)

    plan = db.relationship("Plan")

    @property
    def next_state(self):
        i = self.STATES.index(self.state)
        return self.STATES[i + 1] if i + 1 < len(self.STATES) else None