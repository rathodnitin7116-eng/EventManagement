from flask import Blueprint, render_template, redirect, url_for, abort
from flask_login import login_required, current_user
from ..database import test_connection,get_connection

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

    connection = get_connection()

    try:
        cursor = connection.cursor(dictionary=True)
        organizer_id = int(current_user.id)

        # Organizer approval status
        cursor.execute("""
            SELECT approval_status, organization_name
            FROM organizer_profiles
            WHERE organizer_id = %s
        """, (organizer_id,))
        profile = cursor.fetchone()

        # Event statistics
        cursor.execute("""
            SELECT
                COUNT(*) AS total_events,
                SUM(event_status = 'PUBLISHED') AS published_events,
                SUM(event_status = 'PENDING_APPROVAL') AS pending_events
            FROM events
            WHERE organizer_id = %s
        """, (organizer_id,))
        stats = cursor.fetchone()

        # Total confirmed bookings for organizer's events
        cursor.execute("""
            SELECT COUNT(DISTINCT b.booking_id) AS total_bookings
            FROM bookings b
            JOIN booking_details bd
                ON bd.booking_id = b.booking_id
            JOIN ticket_types tt
                ON tt.ticket_type_id = bd.ticket_type_id
            JOIN events e
                ON e.event_id = tt.event_id
            WHERE e.organizer_id = %s
            AND b.booking_status = 'CONFIRMED'
        """, (organizer_id,))
        booking_stats = cursor.fetchone()

        # Recent events
        cursor.execute("""
            SELECT event_name, start_at, event_status
            FROM events
            WHERE organizer_id = %s
            ORDER BY created_at DESC
            LIMIT 5
        """, (organizer_id,))
        recent_events = cursor.fetchall()

        cursor.close()

        return render_template(
            "dashboards/organizer.html",
            profile=profile,
            stats=stats,
            total_bookings=booking_stats["total_bookings"],
            recent_events=recent_events
        )

    finally:
        connection.close()


