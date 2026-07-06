"""
SupplyLink — app.py
All routes: auth, dashboards (per portal), inventory, suppliers, POs, requisitions.
(Only auth + the four post-login dashboard routes are implemented so far —
inventory/suppliers/PO/requisition CRUD routes come next.)
"""

from functools import wraps

from flask import Flask, render_template, redirect, url_for, request, flash
from flask_login import (
    login_user, logout_user, login_required, current_user
)

from config import Config
from extensions import db, login_manager
from models import User, Requisition


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
        return render_template("admin/dashboard.html")

    # ---- Supply Chain portal ----
    @app.route("/dashboard/supply-chain")
    @supply_chain_required
    def supply_chain_dashboard():
        return render_template("supply_chain/dashboard.html")

    # ---- Pharmacy portal ----
    @app.route("/dashboard/pharmacy")
    @pharmacy_required
    def pharmacy_dashboard():
        return render_template("pharmacy/dashboard.html")

    # ---- Lab portal ----
    @app.route("/dashboard/lab")
    @lab_required
    def lab_dashboard():
        return render_template("lab/dashboard.html")

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