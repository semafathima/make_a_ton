"""Billing, Payment & Finance Dashboard module.

Run:
    pip install flask flask-sqlalchemy
    flask --app app seed      # optional demo data
    flask --app app run --debug

Money is stored as integer cents to avoid floating-point errors.
"""
import os
import secrets
from calendar import monthrange
from datetime import date, timedelta
from decimal import Decimal, InvalidOperation

from flask import (Flask, abort, flash, redirect, render_template, request,
                   session, url_for)
from sqlalchemy import func

from extensions import db  # CHANGED: shared db (was: from flask_sqlalchemy import SQLAlchemy)

app = Flask(__name__)
app.config.update(
    SECRET_KEY=os.environ.get("SECRET_KEY", "dev-change-me"),
    SQLALCHEMY_DATABASE_URI=os.environ.get("DATABASE_URL", "sqlite:///billing.db"),
    SQLALCHEMY_TRACK_MODIFICATIONS=False,
    PAYMENT_TERM_DAYS=14,  # invoice due date = billing date + this many days
    CURRENCY="$",
)
db.init_app(app)  # CHANGED: was db = SQLAlchemy(app)

CYCLE_MONTHS = {"monthly": 1, "quarterly": 3, "yearly": 12}
PAYMENT_METHODS = ["Card", "Bank transfer", "Cash", "Cheque", "Other"]


# --------------------------------------------------------------------------
# Models
# --------------------------------------------------------------------------
def add_months(d: date, n: int) -> date:
    m = d.month - 1 + n
    y, m = d.year + m // 12, m % 12 + 1
    return date(y, m, min(d.day, monthrange(y, m)[1]))


class Subscription(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    customer_name = db.Column(db.String(120), nullable=False)
    plan = db.Column(db.String(80), nullable=False)
    amount_cents = db.Column(db.Integer, nullable=False)
    cycle = db.Column(db.String(10), nullable=False, default="monthly")
    start_date = db.Column(db.Date, nullable=False)
    status = db.Column(db.String(10), nullable=False, default="active")  # active | cancelled
    periods_billed = db.Column(db.Integer, nullable=False, default=0)
    invoices = db.relationship("Invoice", backref="subscription", lazy=True)

    @property
    def next_billing_date(self) -> date:
        # Computed from start_date so month-end dates never drift (Jan 31 -> Feb 28 -> Mar 31)
        return add_months(self.start_date, CYCLE_MONTHS[self.cycle] * self.periods_billed)

    @property
    def monthly_cents(self) -> float:
        return self.amount_cents / CYCLE_MONTHS[self.cycle]


class Invoice(db.Model):
    __table_args__ = (db.UniqueConstraint("subscription_id", "billing_date"),)
    id = db.Column(db.Integer, primary_key=True)
    subscription_id = db.Column(db.Integer, db.ForeignKey("subscription.id"), nullable=False)
    billing_date = db.Column(db.Date, nullable=False)
    issue_date = db.Column(db.Date, nullable=False)
    due_date = db.Column(db.Date, nullable=False)
    amount_cents = db.Column(db.Integer, nullable=False)
    status = db.Column(db.String(10), nullable=False, default="Pending")  # Pending | Paid | Overdue
    payments = db.relationship("Payment", backref="invoice", lazy=True,
                               order_by="Payment.paid_on")

    @property
    def number(self) -> str:
        return f"INV-{self.id:05d}"

    @property
    def paid_cents(self) -> int:
        return sum(p.amount_cents for p in self.payments)

    @property
    def balance_cents(self) -> int:
        return max(self.amount_cents - self.paid_cents, 0)


class Payment(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    invoice_id = db.Column(db.Integer, db.ForeignKey("invoice.id"), nullable=False)
    amount_cents = db.Column(db.Integer, nullable=False)
    method = db.Column(db.String(30), nullable=False)
    reference = db.Column(db.String(80))
    paid_on = db.Column(db.Date, nullable=False)
    notes = db.Column(db.String(255))


# --------------------------------------------------------------------------
# Billing logic
# --------------------------------------------------------------------------
def run_billing_cycle(today: date | None = None) -> int:
    """Create an invoice for every active subscription whose billing date has arrived.

    Idempotent: periods_billed advances with each invoice, and a unique constraint on
    (subscription_id, billing_date) backs it up. Catches up on missed periods.
    """
    today = today or date.today()
    created = 0
    subs = db.session.execute(db.select(Subscription).filter_by(status="active")).scalars()
    for sub in subs:
        while sub.next_billing_date <= today:
            bd = sub.next_billing_date
            db.session.add(Invoice(
                subscription_id=sub.id, billing_date=bd, issue_date=bd,
                due_date=bd + timedelta(days=app.config["PAYMENT_TERM_DAYS"]),
                amount_cents=sub.amount_cents, status="Pending"))
            sub.periods_billed += 1
            created += 1
    db.session.commit()
    return created


def refresh_overdue(today: date | None = None) -> None:
    """Unpaid invoices past their due date become Overdue."""
    today = today or date.today()
    db.session.execute(
        db.update(Invoice)
        .where(Invoice.status == "Pending", Invoice.due_date < today)
        .values(status="Overdue"))
    db.session.commit()


def to_cents(raw: str) -> int | None:
    try:
        value = Decimal(raw.strip())
    except (InvalidOperation, AttributeError):
        return None
    if value <= 0 or value.as_tuple().exponent < -2:
        return None
    return int(value * 100)


# --------------------------------------------------------------------------
# CSRF + template helpers
# --------------------------------------------------------------------------
@app.before_request
def csrf_protect():
    if request.method == "POST":
        token = session.get("csrf_token")
        if not token or token != request.form.get("csrf_token"):
            abort(400, "Invalid CSRF token")


@app.context_processor
def inject_helpers():
    def csrf_token():
        if "csrf_token" not in session:
            session["csrf_token"] = secrets.token_hex(16)
        return session["csrf_token"]
    return {"csrf_token": csrf_token}


@app.template_filter("money")
def money(cents):
    return f"{app.config['CURRENCY']}{(cents or 0) / 100:,.2f}"


# --------------------------------------------------------------------------
# Routes
# --------------------------------------------------------------------------
@app.route("/")
def index():
    return redirect(url_for("dashboard"))


@app.route("/invoices")
def invoices():
    run_billing_cycle()   # auto-generate anything that has come due
    refresh_overdue()     # flip Pending -> Overdue where due_date has passed

    status = request.args.get("status", "all")
    query = db.select(Invoice).order_by(Invoice.billing_date.desc(), Invoice.id.desc())
    if status in ("Pending", "Paid", "Overdue"):
        query = query.filter_by(status=status)
    rows = db.session.execute(query).scalars().all()
    return render_template("invoices.html", invoices=rows, status=status, today=date.today())


@app.route("/invoices/generate", methods=["POST"])
def generate_invoices():
    created = run_billing_cycle()
    refresh_overdue()
    flash(f"{created} new invoice(s) generated." if created
          else "No subscriptions are due for billing.", "success" if created else "info")
    return redirect(url_for("invoices"))


@app.route("/payments", methods=["GET", "POST"])
def payments():
    refresh_overdue()
    open_invoices = db.session.execute(
        db.select(Invoice).where(Invoice.status.in_(["Pending", "Overdue"]))
        .order_by(Invoice.due_date)).scalars().all()

    if request.method == "POST":
        invoice = db.session.get(Invoice, request.form.get("invoice_id", type=int) or 0)
        amount = to_cents(request.form.get("amount", ""))
        method = request.form.get("method", "")
        try:
            paid_on = date.fromisoformat(request.form.get("paid_on", ""))
        except ValueError:
            paid_on = None

        error = None
        if invoice is None or invoice.status == "Paid":
            error = "Choose an open invoice."
        elif amount is None:
            error = "Enter a valid amount greater than zero (max 2 decimals)."
        elif amount > invoice.balance_cents:
            error = f"Amount exceeds the outstanding balance of {money(invoice.balance_cents)}."
        elif method not in PAYMENT_METHODS:
            error = "Choose a payment method."
        elif paid_on is None or paid_on > date.today():
            error = "Enter a valid payment date (not in the future)."

        if error:
            flash(error, "danger")
        else:
            db.session.add(Payment(
                invoice_id=invoice.id, amount_cents=amount, method=method,
                reference=request.form.get("reference", "").strip()[:80] or None,
                notes=request.form.get("notes", "").strip()[:255] or None,
                paid_on=paid_on))
            db.session.flush()
            db.session.refresh(invoice)
            if invoice.balance_cents == 0:
                invoice.status = "Paid"
            elif invoice.due_date < date.today():
                invoice.status = "Overdue"
            db.session.commit()
            flash(f"Recorded {money(amount)} against {invoice.number}"
                  f"{' - invoice is now Paid.' if invoice.status == 'Paid' else '.'}", "success")
            return redirect(url_for("payments"))

    recent = db.session.execute(
        db.select(Payment).order_by(Payment.paid_on.desc(), Payment.id.desc()).limit(15)
    ).scalars().all()
    return render_template("payments.html", open_invoices=open_invoices, recent=recent,
                           methods=PAYMENT_METHODS, today=date.today(),
                           selected=request.values.get("invoice_id", type=int))


@app.route("/dashboard")
def dashboard():
    refresh_overdue()
    active = db.session.execute(db.select(Subscription).filter_by(status="active")).scalars().all()
    revenue = db.session.scalar(db.select(func.coalesce(func.sum(Payment.amount_cents), 0)))

    pending = db.session.execute(db.select(Invoice).filter_by(status="Pending")).scalars().all()
    overdue = db.session.execute(
        db.select(Invoice).filter_by(status="Overdue").order_by(Invoice.due_date)).scalars().all()

    stats = {
        "active_subscriptions": len(active),
        "mrr_cents": round(sum(s.monthly_cents for s in active)),
        "revenue_cents": revenue,
        "pending_count": len(pending),
        "pending_cents": sum(i.balance_cents for i in pending),
        "overdue_count": len(overdue),
        "overdue_cents": sum(i.balance_cents for i in overdue),
    }
    return render_template("dashboard.html", stats=stats, overdue=overdue[:10], today=date.today())


# --------------------------------------------------------------------------
# ADDED: Subscription & Product module (blueprints in routes/, models in models.py)
# --------------------------------------------------------------------------
from routes.products import bp as products_bp
from routes.subscriptions import bp as subscriptions_bp
from routes.discounts import bp as discounts_bp

app.register_blueprint(products_bp)
app.register_blueprint(subscriptions_bp)
app.register_blueprint(discounts_bp)


@app.context_processor
def inject_currency():
    return {"cur": app.config["CURRENCY"]}


# --------------------------------------------------------------------------
# Setup / demo data
# --------------------------------------------------------------------------
with app.app_context():
    import models  # noqa: F401  (ADDED: registers Product, Plan, Quote... tables)
    db.create_all()


@app.cli.command("seed")
def seed():
    """Insert demo subscriptions (billing dates in the past, so invoices generate)."""
    today = date.today()
    demo = [
        ("Acme Corp", "Pro", 4900, "monthly", add_months(today, -3)),
        ("Globex Ltd", "Enterprise", 49900, "quarterly", add_months(today, -6)),
        ("Initech", "Starter", 1900, "monthly", add_months(today, -1)),
        ("Umbrella Inc", "Pro (annual)", 49000, "yearly", add_months(today, -12)),
        ("Hooli", "Pro", 4900, "monthly", today + timedelta(days=10)),
    ]
    for name, plan, cents, cycle, start in demo:
        db.session.add(Subscription(customer_name=name, plan=plan, amount_cents=cents,
                                    cycle=cycle, start_date=start))
    db.session.commit()
    print(f"Seeded {len(demo)} subscriptions.")


if __name__ == "__main__":
    app.run(debug=True)