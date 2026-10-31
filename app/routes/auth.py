from flask import Blueprint, render_template, request, redirect, url_for, flash
from flask_login import login_user, logout_user, login_required, current_user
from werkzeug.security import generate_password_hash, check_password_hash
from mysql.connector import IntegrityError
from ..database import get_connection
from ..models import User

auth_bp = Blueprint("auth", __name__)

@auth_bp.route("/register", methods=["GET", "POST"])
def register():
    if current_user.is_authenticated:
        return redirect(url_for("pages.dashboard"))

    if request.method == "POST":
        full_name = request.form.get("full_name", "").strip()
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")
        role = request.form.get("role", "CUSTOMER").upper()

        if role not in ("CUSTOMER", "ORGANIZER"):
            flash("Invalid account type.", "error")
            return render_template("auth/register.html")

        if not full_name or not email or len(password) < 8:
            flash("Enter your name and email. Password must be at least 8 characters.", "error")
            return render_template("auth/register.html")

        connection = get_connection()
        try:
            cursor = connection.cursor()
            cursor.execute(
                """INSERT INTO users (full_name, email, password_hash, role)
                   VALUES (%s, %s, %s, %s)""",
                (full_name, email, generate_password_hash(password), role),
            )
            user_id = cursor.lastrowid

            if role == "ORGANIZER":
                organization_name = request.form.get("organization_name", "").strip()
                if not organization_name:
                    connection.rollback()
                    flash("Organization name is required for organizer registration.", "error")
                    return render_template("auth/register.html")
                cursor.execute(
                    """INSERT INTO organizer_profiles
                       (organizer_id, organization_name, approval_status)
                       VALUES (%s, %s, 'PENDING')""",
                    (user_id, organization_name),
                )

            connection.commit()
            cursor.close()
            flash("Registration successful. You can now log in.", "success")
            return redirect(url_for("auth.login"))
        except IntegrityError:
            connection.rollback()
            flash("That email address is already registered.", "error")
        except Exception:
            connection.rollback()
            raise
        finally:
            connection.close()

    return render_template("auth/register.html")

@auth_bp.route("/login", methods=["GET", "POST"])
def login():
    if current_user.is_authenticated:
        return redirect(url_for("pages.dashboard"))

    if request.method == "POST":
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")
        connection = get_connection()
        try:
            cursor = connection.cursor(dictionary=True)
            cursor.execute(
                """SELECT user_id, full_name, email, password_hash, role, account_status
                   FROM users WHERE email = %s""",
                (email,),
            )
            row = cursor.fetchone()
            cursor.close()
        finally:
            connection.close()

        if row and row["account_status"] == "ACTIVE" and check_password_hash(row["password_hash"], password):
            user = User(row["user_id"], row["full_name"], row["email"],
                        row["role"], row["account_status"])
            login_user(user)
            return redirect(url_for("pages.dashboard"))

        flash("Invalid email/password or inactive account.", "error")

    return render_template("auth/login.html")

@auth_bp.route("/logout", methods=["POST"])
@login_required
def logout():
    logout_user()
    flash("You have been logged out.", "success")
    return redirect(url_for("auth.login"))
