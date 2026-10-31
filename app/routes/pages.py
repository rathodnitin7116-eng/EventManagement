from flask import Blueprint, render_template, redirect, url_for, abort
from flask_login import login_required, current_user
from ..database import test_connection

pages_bp = Blueprint("pages", __name__)

@pages_bp.route("/")
def home():
    return render_template("home.html")

@pages_bp.route("/health")
def health():
    ok, result = test_connection()
    if not ok:
        return {"status": "database_error", "detail": result}, 500
    return {"status": "ok", "mysql_version": result}

@pages_bp.route("/dashboard")
@login_required
def dashboard():
    if current_user.role == "ADMIN":
        return redirect(url_for("admin.dashboard"))
    if current_user.role == "ORGANIZER":
        return redirect(url_for("pages.organizer_dashboard"))
    return redirect(url_for("pages.customer_dashboard"))

@pages_bp.route("/customer/dashboard")
@login_required
def customer_dashboard():
    if current_user.role != "CUSTOMER":
        abort(403)
    return render_template("dashboards/customer.html")

@pages_bp.route("/organizer/dashboard")
@login_required
def organizer_dashboard():
    if current_user.role != "ORGANIZER":
        abort(403)
    return render_template("dashboards/organizer.html")


