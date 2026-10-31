from functools import wraps
from flask import Blueprint, render_template, request, redirect, url_for, flash, abort
from flask_login import login_required, current_user
from mysql.connector import Error
from ..database import get_connection

admin_bp = Blueprint("admin", __name__, url_prefix="/admin")

def admin_required(view):
    @wraps(view)
    @login_required
    def wrapped(*args, **kwargs):
        if current_user.role != "ADMIN":
            abort(403)
        return view(*args, **kwargs)
    return wrapped

@admin_bp.route("/dashboard")
@admin_required
def dashboard():
    connection = get_connection()
    try:
        cursor = connection.cursor(dictionary=True)
        cursor.execute("SELECT COUNT(*) AS total FROM users")
        total_users = cursor.fetchone()["total"]
        cursor.execute("SELECT COUNT(*) AS total FROM events")
        total_events = cursor.fetchone()["total"]
        cursor.execute("SELECT COUNT(*) AS total FROM bookings WHERE booking_status = 'CONFIRMED'")
        total_bookings = cursor.fetchone()["total"]
        cursor.execute("""
            SELECT COALESCE(SUM(amount), 0) AS total
            FROM payments WHERE payment_status = 'SUCCESS'
        """)
        revenue = cursor.fetchone()["total"]
        cursor.execute("""
            SELECT COUNT(*) AS total FROM organizer_profiles
            WHERE approval_status = 'PENDING'
        """)
        pending_organizers = cursor.fetchone()["total"]
        cursor.execute("""
            SELECT COUNT(*) AS total FROM events
            WHERE event_status = 'PENDING_APPROVAL'
        """)
        pending_events = cursor.fetchone()["total"]
        cursor.execute("""
            SELECT COUNT(*) AS total FROM venue_requests
            WHERE request_status = 'PENDING'
        """)
        pending_venue_requests = cursor.fetchone()["total"]
        cursor.execute("""
            SELECT e.event_id, e.event_name, e.start_at, e.event_status,
                   u.full_name AS organizer_name, c.category_name
            FROM events e
            JOIN users u ON u.user_id = e.organizer_id
            JOIN categories c ON c.category_id = e.category_id
            ORDER BY e.created_at DESC LIMIT 6
        """)
        recent_events = cursor.fetchall()
        cursor.close()
        return render_template(
            "admin/dashboard.html",
            total_users=total_users, total_events=total_events,
            total_bookings=total_bookings, revenue=revenue,
            pending_organizers=pending_organizers,
            pending_events=pending_events,
            pending_venue_requests=pending_venue_requests,
            recent_events=recent_events,
        )
    finally:
        connection.close()

@admin_bp.route("/organizers")
@admin_required
def organizers():
    connection = get_connection()
    try:
        cursor = connection.cursor(dictionary=True)
        cursor.execute("""
            SELECT u.user_id, u.full_name, u.email, u.created_at,
                   op.organization_name, op.approval_status
            FROM organizer_profiles op
            JOIN users u ON u.user_id = op.organizer_id
            ORDER BY FIELD(op.approval_status, 'PENDING', 'APPROVED', 'REJECTED'),
                     op.created_at DESC
        """)
        rows = cursor.fetchall()
        cursor.close()
        return render_template("admin/organizers.html", organizers=rows)
    finally:
        connection.close()

@admin_bp.post("/organizers/<int:organizer_id>/review")
@admin_required
def review_organizer(organizer_id):
    decision = request.form.get("decision")
    if decision not in ("APPROVED", "REJECTED"):
        abort(400)
    connection = get_connection()
    try:
        cursor = connection.cursor()
        cursor.execute("""
            UPDATE organizer_profiles
            SET approval_status=%s, reviewed_by=%s, reviewed_at=NOW()
            WHERE organizer_id=%s AND approval_status='PENDING'
        """, (decision, int(current_user.id), organizer_id))
        connection.commit()
        if cursor.rowcount:
            flash(f"Organizer {decision.lower()}.", "success")
        else:
            flash("No pending organizer request was found.", "info")
        cursor.close()
    except Error:
        connection.rollback()
        raise
    finally:
        connection.close()
    return redirect(url_for("admin.organizers"))

@admin_bp.route("/events")
@admin_required
def events():
    connection = get_connection()
    try:
        cursor = connection.cursor(dictionary=True)
        cursor.execute("""
            SELECT e.event_id, e.event_name, e.start_at, e.end_at, e.event_status,
                   e.venue_id, u.full_name AS organizer_name, c.category_name,
                   v.venue_name
            FROM events e
            JOIN users u ON u.user_id=e.organizer_id
            JOIN categories c ON c.category_id=e.category_id
            LEFT JOIN venues v ON v.venue_id=e.venue_id
            ORDER BY FIELD(e.event_status, 'PENDING_APPROVAL', 'DRAFT', 'PUBLISHED',
                           'REJECTED', 'CANCELLED', 'COMPLETED'),
                     e.created_at DESC
        """)
        rows = cursor.fetchall()
        cursor.close()
        return render_template("admin/events.html", events=rows)
    finally:
        connection.close()

@admin_bp.post("/events/<int:event_id>/review")
@admin_required
def review_event(event_id):
    decision = request.form.get("decision")
    if decision not in ("PUBLISHED", "REJECTED"):
        abort(400)
    connection = get_connection()
    try:
        cursor = connection.cursor(dictionary=True)
        cursor.execute("""
            SELECT e.event_id, e.venue_id, e.start_at, e.end_at, e.event_status,
                   op.approval_status AS organizer_status
            FROM events e
            JOIN organizer_profiles op ON op.organizer_id=e.organizer_id
            WHERE e.event_id=%s FOR UPDATE
        """, (event_id,))
        event = cursor.fetchone()
        if not event or event["event_status"] != "PENDING_APPROVAL":
            connection.rollback()
            flash("This event is not awaiting approval.", "info")
        elif decision == "PUBLISHED" and (not event["venue_id"] or event["organizer_status"] != "APPROVED"):
            connection.rollback()
            flash("A published event needs an approved organizer and an allocated venue.", "error")
        else:
            cursor.execute("""
                UPDATE events SET event_status=%s,
                    rejection_reason=%s
                WHERE event_id=%s
            """, (
                decision,
                request.form.get("reason", "").strip() if decision == "REJECTED" else None,
                event_id,
            ))
            connection.commit()
            flash(f"Event {decision.lower()}.", "success")
        cursor.close()
    except Error:
        connection.rollback()
        raise
    finally:
        connection.close()
    return redirect(url_for("admin.events"))

@admin_bp.route("/venue-requests")
@admin_required
def venue_requests():
    connection = get_connection()
    try:
        cursor = connection.cursor(dictionary=True)
        cursor.execute("""
            SELECT vr.venue_request_id, vr.event_id, vr.venue_id, vr.request_note,
                   vr.request_status, vr.created_at, e.event_name, e.start_at, e.end_at,
                   v.venue_name, v.capacity, u.full_name AS organizer_name
            FROM venue_requests vr
            JOIN events e ON e.event_id=vr.event_id
            JOIN venues v ON v.venue_id=vr.venue_id
            JOIN users u ON u.user_id=vr.requested_by
            ORDER BY FIELD(vr.request_status, 'PENDING', 'APPROVED', 'REJECTED', 'WITHDRAWN'),
                     vr.created_at DESC
        """)
        rows = cursor.fetchall()
        cursor.close()
        return render_template("admin/venue_requests.html", requests=rows)
    finally:
        connection.close()

@admin_bp.post("/venue-requests/<int:request_id>/review")
@admin_required
def review_venue_request(request_id):
    decision = request.form.get("decision")
    if decision not in ("APPROVED", "REJECTED"):
        abort(400)
    connection = get_connection()
    try:
        cursor = connection.cursor(dictionary=True)
        cursor.execute("""
            SELECT vr.venue_request_id, vr.event_id, vr.venue_id, vr.request_status,
                   e.start_at, e.end_at
            FROM venue_requests vr
            JOIN events e ON e.event_id=vr.event_id
            WHERE vr.venue_request_id=%s FOR UPDATE
        """, (request_id,))
        row = cursor.fetchone()
        if not row or row["request_status"] != "PENDING":
            connection.rollback()
            flash("This venue request is no longer pending.", "info")
        elif decision == "APPROVED":
            cursor.execute("""
                SELECT COUNT(*) AS conflicts
                FROM events
                WHERE venue_id=%s
                  AND event_id<>%s
                  AND event_status IN ('PUBLISHED', 'PENDING_APPROVAL')
                  AND start_at < %s AND end_at > %s
                FOR UPDATE
            """, (row["venue_id"], row["event_id"], row["end_at"], row["start_at"]))
            conflict = cursor.fetchone()["conflicts"]
            if conflict:
                connection.rollback()
                flash("Venue allocation conflicts with another scheduled event.", "error")
            else:
                cursor.execute("""
                    UPDATE venue_requests
                    SET request_status='APPROVED', reviewed_by=%s,
                        reviewed_at=NOW(), admin_note=%s
                    WHERE venue_request_id=%s
                """, (int(current_user.id), request.form.get("note", "").strip(), request_id))
                cursor.execute("UPDATE events SET venue_id=%s WHERE event_id=%s",
                               (row["venue_id"], row["event_id"]))
                connection.commit()
                flash("Venue request approved and venue assigned to the event.", "success")
        else:
            cursor.execute("""
                UPDATE venue_requests
                SET request_status='REJECTED', reviewed_by=%s,
                    reviewed_at=NOW(), admin_note=%s
                WHERE venue_request_id=%s
            """, (int(current_user.id), request.form.get("note", "").strip(), request_id))
            connection.commit()
            flash("Venue request rejected.", "success")
        cursor.close()
    except Error:
        connection.rollback()
        raise
    finally:
        connection.close()
    return redirect(url_for("admin.venue_requests"))

@admin_bp.route("/venues", methods=["GET", "POST"])
@admin_required
def venues():
    connection = get_connection()
    try:
        if request.method == "POST":
            name = request.form.get("venue_name", "").strip()
            address = request.form.get("address_line", "").strip()
            city = request.form.get("city", "").strip()
            capacity_raw = request.form.get("capacity", "").strip()
            if not name or not address or not city:
                flash("Venue name, address and city are required.", "error")
            else:
                try:
                    capacity = int(capacity_raw)
                    if capacity <= 0:
                        raise ValueError
                    cursor = connection.cursor()
                    cursor.execute("""
                        INSERT INTO venues
                          (venue_name, address_line, city, state, postal_code, capacity, facilities)
                        VALUES (%s,%s,%s,%s,%s,%s,%s)
                    """, (
                        name, address, city,
                        request.form.get("state", "").strip() or None,
                        request.form.get("postal_code", "").strip() or None,
                        capacity,
                        request.form.get("facilities", "").strip() or None,
                    ))
                    connection.commit()
                    cursor.close()
                    flash("Venue added successfully.", "success")
                except ValueError:
                    flash("Capacity must be a positive whole number.", "error")
        cursor = connection.cursor(dictionary=True)
        cursor.execute("SELECT * FROM venues ORDER BY created_at DESC")
        rows = cursor.fetchall()
        cursor.close()
        return render_template("admin/venues.html", venues=rows)
    finally:
        connection.close()
