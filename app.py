"""
SupplyLink — app.py
All routes: auth, dashboards (per portal), inventory, suppliers, POs, requisitions.
(Only auth + the four post-login dashboard routes are implemented so far —
inventory/suppliers/PO/requisition CRUD routes come next.)
"""

from functools import wraps
from datetime import datetime

from flask import Flask, render_template, redirect, url_for, request, flash
from flask_login import (
    login_user, logout_user, login_required, current_user
)

from config import Config
from extensions import db, login_manager
from models import User, Requisition, Department


def create_app():
    app = Flask(__name__)
    app.config.from_object(Config)

    db.init_app(app)
    login_manager.init_app(app)

    with app.app_context():
        import models  # noqa: F401 — ensures models are registered before create_all
        db.create_all()

    register_routes(app)
    return app


# ---------------------------------------------------------------------------
# Access control decorators — one per portal, matching templates/<portal>/
# ---------------------------------------------------------------------------

def admin_required(view_func):
    @wraps(view_func)
    def wrapped(*args, **kwargs):
        if not current_user.is_authenticated:
            return login_manager.unauthorized()
        if not current_user.is_admin:
            flash("That page is only available to Admin.", "warning")
            return redirect(url_for("post_login_redirect"))
        return view_func(*args, **kwargs)
    return wrapped


def supply_chain_required(view_func):
    """Restrict a route to users in the Supply Chain department.
    Other staff get redirected back to their own dashboard with a flash
    message instead of a 403, since this is an internal staff tool."""
    @wraps(view_func)
    def wrapped(*args, **kwargs):
        if not current_user.is_authenticated:
            return login_manager.unauthorized()
        if not current_user.department.is_supply_chain:
            flash("That page is only available to the Supply Chain department.", "warning")
            return redirect(url_for("post_login_redirect"))
        return view_func(*args, **kwargs)
    return wrapped


def department_required(department_name):
    """Factory for portals tied to a specific department name (Pharmacy, Lab, ...)."""
    def decorator(view_func):
        @wraps(view_func)
        def wrapped(*args, **kwargs):
            if not current_user.is_authenticated:
                return login_manager.unauthorized()
            dept_name = (current_user.department.name or "").strip().lower()
            if dept_name != department_name.lower():
                flash(f"That page is only available to {department_name}.", "warning")
                return redirect(url_for("post_login_redirect"))
            return view_func(*args, **kwargs)
        return wrapped
    return decorator


pharmacy_required = department_required("Pharmacy")
lab_required = department_required("Lab")


def check_portal_match(user, login_as):
    """Validate that the portal the person picked on the login screen
    actually matches their real account. Returns an error message string
    if there's a mismatch, or None if it's fine. This doesn't grant any
    access on its own — actual permissions still come from user.role and
    user.department in the database — it just catches someone picking
    the wrong portal by mistake and tells them clearly."""
    dept_name = (user.department.name or "").strip().lower()

    if login_as == "admin":
        if not user.is_admin:
            return "This account isn't an Admin account. Choose your correct portal below."
    elif login_as == "supply_chain":
        if not user.department.is_supply_chain:
            return "This account isn't part of Supply Chain. Choose your correct portal below."
    elif login_as == "pharmacy":
        if dept_name != "pharmacy":
            return "This account isn't part of Pharmacy. Choose your correct portal below."
    elif login_as == "lab":
        if dept_name != "lab":
            return "This account isn't part of the Lab. Choose your correct portal below."
    else:
        return "Please select which portal you're signing in to."

    return None


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

def register_routes(app):

    @app.route("/")
    def home():
        if current_user.is_authenticated:
            return redirect(url_for("post_login_redirect"))
        return render_template("landing_page.html")

    @app.route("/login", methods=["GET", "POST"])
    def login():
        if current_user.is_authenticated:
            return redirect(url_for("post_login_redirect"))

        if request.method == "POST":
            email = request.form.get("email", "").strip().lower()
            password = request.form.get("password", "")
            remember = bool(request.form.get("remember"))
            login_as = request.form.get("login_as", "")

            user = User.query.filter_by(email=email).first()

            if user is None or not user.check_password(password):
                flash("Invalid email or password.", "error")
                return render_template("login.html", email=email, login_as=login_as), 401

            portal_error = check_portal_match(user, login_as)
            if portal_error:
                flash(portal_error, "error")
                return render_template("login.html", email=email, login_as=login_as), 403

            login_user(user, remember=remember)
            flash(f"Welcome back, {user.name.split()[0]}.", "success")

            next_url = request.args.get("next")
            if next_url:
                return redirect(next_url)
            return redirect(url_for("post_login_redirect"))

        return render_template("login.html")

    @app.route("/logout")
    @login_required
    def logout():
        logout_user()
        flash("You've been logged out.", "info")
        return redirect(url_for("login"))

    @app.route("/post-login")
    @login_required
    def post_login_redirect():
        """Single entry point after login — routes each user to the
        dashboard for their portal: Admin, Supply Chain, Pharmacy, or Lab.
        Falls back to Supply Chain's own view of requisitions-only staff
        (departments without a dedicated dashboard yet) via my_requisitions."""
        if current_user.is_admin:
            return redirect(url_for("admin_dashboard"))
        if current_user.department.is_supply_chain:
            return redirect(url_for("supply_chain_dashboard"))

        dept_name = (current_user.department.name or "").strip().lower()
        if dept_name == "pharmacy":
            return redirect(url_for("pharmacy_dashboard"))
        if dept_name == "lab":
            return redirect(url_for("lab_dashboard"))

        # Department has no dedicated dashboard template yet — send them
        # to their requisitions list instead of a 404.
        return redirect(url_for("my_requisitions"))

    # ---- Admin portal ----
    @app.route("/dashboard/admin")
    @admin_required
    def admin_dashboard():
        total_users = User.query.count()
        total_departments = Department.query.count()

        try:
            pending_requisitions = Requisition.query.filter_by(status="Pending").count()
        except Exception:
            pending_requisitions = 0

        # Low-stock count depends on the Item model, which may not exist
        # yet in your models.py — guarded so the dashboard never 500s
        # while inventory is still being built.
        try:
            from models import Item
            low_stock_items = Item.query.filter(Item.quantity_on_hand <= Item.reorder_level).count()
        except Exception:
            low_stock_items = 0

        stats = {
            "total_users": total_users,
            "total_departments": total_departments,
            "pending_requisitions": pending_requisitions,
            "low_stock_items": low_stock_items,
        }

        departments = []
        for dept in Department.query.order_by(Department.name.asc()).all():
            staff_count = User.query.filter_by(department_id=dept.id).count()
            fill_pct = min(int((staff_count / total_users) * 100), 100) if total_users else 0
            departments.append({"name": dept.name, "staff_count": staff_count, "fill_pct": fill_pct})

        return render_template(
            "admin/dashboard.html",
            stats=stats,
            departments=departments,
            recent_activity=[],  # populated once an audit-log model exists
            today=datetime.utcnow(),
        )

    @app.route("/admin/users")
    @admin_required
    def admin_users():
        query = User.query
        search = request.args.get("q", "").strip()
        if search:
            query = query.filter(
                (User.name.ilike(f"%{search}%")) | (User.email.ilike(f"%{search}%"))
            )
        department_id = request.args.get("department")
        if department_id:
            query = query.filter_by(department_id=department_id)

        users = query.order_by(User.name.asc()).all()
        departments = Department.query.order_by(Department.name.asc()).all()
        return render_template("admin/users_list.html", users=users, departments=departments)

    @app.route("/admin/users/new", methods=["GET", "POST"])
    @app.route("/admin/users/<int:user_id>/edit", methods=["GET", "POST"])
    @admin_required
    def admin_user_form(user_id=None):
        user = User.query.get_or_404(user_id) if user_id else None
        departments = Department.query.order_by(Department.name.asc()).all()

        if request.method == "POST":
            name = request.form.get("name", "").strip()
            email = request.form.get("email", "").strip().lower()
            department_id = request.form.get("department_id")
            role = request.form.get("role", "staff")
            password = request.form.get("password", "")

            # is_admin is a derived property on User (role == "admin"), not a
            # real column — so the "Grant Admin access" toggle just forces role.
            if request.form.get("is_admin"):
                role = "admin"

            if not name or not email or not department_id:
                flash("Name, email, and department are required.", "error")
                return render_template("admin/user_form.html", user=user, departments=departments), 400

            existing = User.query.filter(User.email == email, User.id != (user.id if user else None)).first()
            if existing:
                flash("Another account already uses that email.", "error")
                return render_template("admin/user_form.html", user=user, departments=departments), 400

            if user is None:
                if not password:
                    flash("Password is required for a new account.", "error")
                    return render_template("admin/user_form.html", user=user, departments=departments), 400
                user = User(name=name, email=email, department_id=department_id, role=role)
                user.set_password(password)
                db.session.add(user)
                flash(f"{name} has been added.", "success")
            else:
                user.name = name
                user.email = email
                user.department_id = department_id
                user.role = role
                if password:
                    user.set_password(password)
                flash(f"{name}'s account has been updated.", "success")

            db.session.commit()
            return redirect(url_for("admin_users"))

        return render_template("admin/user_form.html", user=user, departments=departments)

    # ---- Supply Chain portal ----
    @app.route("/dashboard/supply-chain")
    @supply_chain_required
    def supply_chain_dashboard():
        # Inventory-related stats depend on models (Item, PurchaseOrder,
        # StockMovement) that may not be built yet — each is guarded so
        # this dashboard never 500s while the rest of the app catches up.
        total_items = 0
        low_stock_items = []
        total_stock_value = 0
        try:
            from models import Item
            items = Item.query.all()
            total_items = len(items)
            low_stock_items = [i for i in items if i.quantity_on_hand <= i.reorder_level][:8]
            total_stock_value = sum((i.quantity_on_hand or 0) * (i.unit_cost or 0) for i in items)
        except Exception:
            pass

        open_purchase_orders = 0
        try:
            from models import PurchaseOrder
            open_purchase_orders = PurchaseOrder.query.filter(
                PurchaseOrder.status.in_(["Draft", "Sent"])
            ).count()
        except Exception:
            pass

        recent_movements = []
        try:
            from models import StockMovement
            recent_movements = (
                StockMovement.query.order_by(StockMovement.id.desc()).limit(6).all()
            )
        except Exception:
            pass

        pending_requisition_list = (
            Requisition.query
            .filter_by(status="Pending")
            .order_by(Requisition.created_at.desc())
            .limit(8)
            .all()
        )

        stats = {
            "total_items": total_items,
            "low_stock_count": len(low_stock_items),
            "open_purchase_orders": open_purchase_orders,
            "pending_requisitions": len(pending_requisition_list),
            "total_stock_value": total_stock_value,
        }

        return render_template(
            "supply_chain/dashboard.html",
            stats=stats,
            low_stock_items=low_stock_items,
            recent_movements=recent_movements,
            pending_requisition_list=pending_requisition_list,
            today=datetime.utcnow(),
        )

    # ---- Pharmacy portal ----
    @app.route("/dashboard/pharmacy")
    @pharmacy_required
    def pharmacy_dashboard():
        requisitions = (
            Requisition.query
            .filter_by(department_id=current_user.department_id)
            .order_by(Requisition.created_at.desc())
            .all()
        )
        stats = {
            "pending": sum(1 for r in requisitions if r.status == "Pending"),
            "approved": sum(1 for r in requisitions if r.status == "Approved"),
            "rejected": sum(1 for r in requisitions if r.status == "Rejected"),
            "fulfilled": sum(1 for r in requisitions if r.status == "Fulfilled"),
        }
        return render_template(
            "pharmacy/dashboard.html",
            stats=stats,
            recent_requisitions=requisitions[:6],
            today=datetime.utcnow(),
        )

    # ---- Lab portal ----
    @app.route("/dashboard/lab")
    @lab_required
    def lab_dashboard():
        requisitions = (
            Requisition.query
            .filter_by(department_id=current_user.department_id)
            .order_by(Requisition.created_at.desc())
            .all()
        )
        stats = {
            "pending": sum(1 for r in requisitions if r.status == "Pending"),
            "approved": sum(1 for r in requisitions if r.status == "Approved"),
            "rejected": sum(1 for r in requisitions if r.status == "Rejected"),
            "fulfilled": sum(1 for r in requisitions if r.status == "Fulfilled"),
        }
        return render_template(
            "lab/dashboard.html",
            stats=stats,
            recent_requisitions=requisitions[:6],
            today=datetime.utcnow(),
        )

    # ---- Every department: view their own requisitions ----
    @app.route("/requisitions/mine")
    @login_required
    def my_requisitions():
        if current_user.department.is_supply_chain:
            requisitions = Requisition.query.order_by(Requisition.created_at.desc()).all()
        else:
            requisitions = (
                Requisition.query
                .filter_by(department_id=current_user.department_id)
                .order_by(Requisition.created_at.desc())
                .all()
            )
        return render_template("requisitions/my_requisitions.html", requisitions=requisitions)


app = create_app()

if __name__ == "__main__":
    app.run(debug=True)