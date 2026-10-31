from flask import Blueprint, render_template, redirect, url_for, abort,request, flash
from datetime import datetime
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

@pages_bp.route("/organizer/profile", methods=["GET", "POST"])
@login_required
def organizer_profile():
    if current_user.role != "ORGANIZER":
        abort(403)

    connection = get_connection()

    try:
        cursor = connection.cursor(dictionary=True)

        if request.method == "POST":
            organization_name = request.form.get("organization_name", "").strip()
            phone = request.form.get("phone", "").strip()
            description = request.form.get("description", "").strip()

            if not organization_name:
                flash("Organization name is required.", "error")
            else:
                cursor.execute("""
                    UPDATE organizer_profiles
                    SET organization_name = %s,
                        phone = %s,
                        description = %s
                    WHERE organizer_id = %s
                """, (
                    organization_name,
                    phone or None,
                    description or None,
                    int(current_user.id)
                ))

                connection.commit()
                flash("Organization profile updated successfully.", "success")

                return redirect(url_for("pages.organizer_profile"))

        cursor.execute("""
            SELECT organization_name, phone, description, approval_status
            FROM organizer_profiles
            WHERE organizer_id = %s
        """, (int(current_user.id),))

        profile = cursor.fetchone()

        cursor.close()

        if not profile:
            abort(404)

        return render_template(
            "dashboards/organizer_profile.html",
            profile=profile
        )

    finally:
        connection.close()

@pages_bp.route("/organizer/events/create", methods=["GET", "POST"])
@login_required
def create_event():
    if current_user.role != "ORGANIZER":
        abort(403)

    connection = get_connection()

    try:
        cursor = connection.cursor(dictionary=True)

        # Check organizer approval
        cursor.execute("""
            SELECT approval_status
            FROM organizer_profiles
            WHERE organizer_id = %s
        """, (int(current_user.id),))

        profile = cursor.fetchone()

        if not profile or profile["approval_status"] != "APPROVED":
            cursor.close()
            flash("Your organizer account must be approved before creating events.", "warning")
            return redirect(url_for("pages.organizer_dashboard"))

        # Fetch event categories
        cursor.execute("""
            SELECT category_id, category_name
            FROM categories
            ORDER BY category_name
        """)
        categories = cursor.fetchall()

        if request.method == "POST":
            event_name = request.form.get("event_name", "").strip()
            description = request.form.get("description", "").strip()
            category_id = request.form.get("category_id", "").strip()
            start_at = request.form.get("start_at", "").strip()
            end_at = request.form.get("end_at", "").strip()

            if not all([event_name, category_id, start_at, end_at]):
                flash("Please fill in all required fields.", "error")

            else:
                try:
                    category_id = int(category_id)
                    start_date = datetime.strptime(start_at, "%Y-%m-%dT%H:%M")
                    end_date = datetime.strptime(end_at, "%Y-%m-%dT%H:%M")

                    if end_date <= start_date:
                        raise ValueError("End time must be after start time.")

                    if start_date <= datetime.now():
                        raise ValueError("Event must be scheduled in the future.")

                    cursor.execute("""
                        SELECT category_id
                        FROM categories
                        WHERE category_id = %s
                    """, (category_id,))

                    if not cursor.fetchone():
                        raise ValueError("Please select a valid category.")

                    cursor.execute("""
                        INSERT INTO events
                        (organizer_id, category_id, event_name, description,
                         start_at, end_at, event_status)
                        VALUES (%s, %s, %s, %s, %s, %s, 'PENDING_APPROVAL')
                    """, (
                        int(current_user.id),
                        category_id,
                        event_name,
                        description or None,
                        start_date,
                        end_date
                    ))

                    connection.commit()
                    flash("Event submitted successfully for admin approval!", "success")
                    return redirect(url_for("pages.organizer_dashboard"))

                except ValueError as error:
                    flash(str(error), "error")

        cursor.close()

        return render_template(
            "dashboards/create_event.html",
            categories=categories
        )

    except Exception:
        connection.rollback()
        raise

    finally:
        connection.close()
@pages_bp.route("/organizer/events")
@login_required
def organizer_events():
    if current_user.role != "ORGANIZER":
        abort(403)

    connection = get_connection()

    try:
        cursor = connection.cursor(dictionary=True)

        cursor.execute("""
            SELECT
                e.event_id,
                e.event_name,
                c.category_name,
                e.start_at,
                e.end_at,
                e.event_status
            FROM events e
            JOIN categories c
                ON c.category_id = e.category_id
            WHERE e.organizer_id = %s
            ORDER BY e.created_at DESC
        """, (int(current_user.id),))

        events = cursor.fetchall()
        cursor.close()

        return render_template(
            "dashboards/organizer_events.html",
            events=events
        )

    finally:
        connection.close()