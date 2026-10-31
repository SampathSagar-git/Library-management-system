from datetime import datetime, date
from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify, current_app
from flask_login import login_required, current_user
from bson import ObjectId
from models.database import get_db, log_activity, utc_now
from models.book import Book
from models.reservation import BookReservation, DeskReservation
from models.neo4j_models import neo4j_service

booking_bp = Blueprint('booking', __name__)

# ================= Dedicated Desk Reservation System =================

@booking_bp.route('/desks/book')
@login_required
def desk_booking_view():
    db = get_db(current_app.config)
    today_str = utc_now().strftime('%Y-%m-%d')
    selected_date = request.args.get('date', today_str)

    # All desks
    desks = list(db.desks.find().sort("desk_number", 1))

    # Existing bookings for the selected date
    bookings_on_date = list(db.desk_reservations.find({
        "booking_date": selected_date,
        "status": "confirmed"
    }))

    # Map desk occupancy
    desk_status_map = {}
    for d in desks:
        d_num = d.get('desk_number')
        matching = [b for b in bookings_on_date if b.get('desk_number') == d_num]
        if matching:
            desk_status_map[d_num] = {
                'status': 'reserved',
                'slots': [f"{b.get('start_time')}-{b.get('end_time')}" for b in matching],
                'booked_by_me': any(str(b.get('user_id')) == str(current_user.id) for b in matching)
            }
        else:
            desk_status_map[d_num] = {
                'status': 'available',
                'slots': [],
                'booked_by_me': False
            }

    # User's personal bookings
    my_bookings = [DeskReservation(d) for d in db.desk_reservations.find({
        "user_id": str(current_user.id)
    }).sort("booking_date", -1).limit(10)]

    return render_template(
        'desk_booking.html',
        desks=desks,
        desk_status_map=desk_status_map,
        selected_date=selected_date,
        my_bookings=my_bookings,
        today_date=today_str
    )

@booking_bp.route('/api/desks/availability')
@login_required
def check_desk_availability():
    db = get_db(current_app.config)
    booking_date = request.args.get('date', utc_now().strftime('%Y-%m-%d'))
    start_time = request.args.get('start_time', '09:00')
    duration = int(request.args.get('duration', 2))

    start_min = DeskReservation.parse_time_minutes(start_time)
    end_min = start_min + (duration * 60)
    end_time = f"{end_min // 60:02d}:{end_min % 60:02d}"

    desks = list(db.desks.find())
    confirmed_bookings = list(db.desk_reservations.find({
        "booking_date": booking_date,
        "status": "confirmed"
    }))

    results = {}
    for d in desks:
        num = d.get('desk_number')
        is_occupied = False
        occupied_by_me = False
        occupied_times = []

        for b in confirmed_bookings:
            if b.get('desk_number') == num:
                b_start = DeskReservation.parse_time_minutes(b.get('start_time', '00:00'))
                b_end = DeskReservation.parse_time_minutes(b.get('end_time', '00:00'))
                occupied_times.append(f"{b.get('start_time')} - {b.get('end_time')}")

                # Check overlap
                if max(start_min, b_start) < min(end_min, b_end):
                    is_occupied = True
                    if str(b.get('user_id')) == str(current_user.id):
                        occupied_by_me = True

        status = 'occupied' if is_occupied else 'available'
        results[num] = {
            'desk_number': num,
            'zone': d.get('zone'),
            'status': status,
            'is_occupied': is_occupied,
            'occupied_by_me': occupied_by_me,
            'amenities': {
                'power': d.get('has_power', True),
                'monitor': d.get('has_monitor', False)
            },
            'occupied_times': occupied_times
        }

    return jsonify({
        "date": booking_date,
        "requested_slot": f"{start_time} - {end_time}",
        "desks": results
    })

@booking_bp.route('/desks/reserve', methods=['POST'])
@login_required
def reserve_desk():
    db = get_db(current_app.config)
    desk_number = request.form.get('desk_number', '').strip()
    zone = request.form.get('zone', 'Quiet Study Pods')
    booking_date = request.form.get('booking_date', '').strip()
    start_time = request.form.get('start_time', '').strip()
    duration = int(request.form.get('duration_hours', 2))
    purpose = request.form.get('purpose', 'Individual Study')

    if not desk_number or not booking_date or not start_time:
        flash('Please fill out all booking parameters.', 'warning')
        return redirect(url_for('booking.desk_booking_view'))

    # Validate not past date
    try:
        b_date = datetime.strptime(booking_date, '%Y-%m-%d').date()
        if b_date < utc_now().date():
            flash('Cannot book desks for past dates.', 'warning')
            return redirect(url_for('booking.desk_booking_view'))
    except ValueError:
        flash('Invalid date format.', 'danger')
        return redirect(url_for('booking.desk_booking_view'))

    booking, err = DeskReservation.create(
        db, current_user, desk_number=desk_number, zone=zone,
        booking_date=booking_date, start_time=start_time,
        duration_hours=duration, purpose=purpose
    )

    if err:
        flash(err, 'danger')
    else:
        flash(f'Desk {desk_number} successfully reserved for {booking_date} ({start_time} - {booking.end_time})!', 'success')

    return redirect(url_for('booking.desk_booking_view', date=booking_date))

@booking_bp.route('/desks/cancel/<booking_id>', methods=['POST'])
@login_required
def cancel_desk(booking_id):
    db = get_db(current_app.config)
    success, err = DeskReservation.cancel(db, booking_id, current_user)
    if success:
        flash('Desk reservation cancelled.', 'info')
    else:
        flash(f'Failed to cancel: {err}', 'danger')
    return redirect(request.referrer or url_for('booking.desk_booking_view'))

# ================= Book Reservation System =================

@booking_bp.route('/reservations')
@login_required
def reservations_view():
    db = get_db(current_app.config)
    user_id = str(current_user.id)

    if current_user.is_admin:
        reservations = [BookReservation(d) for d in db.book_reservations.find().sort("reservation_date", -1)]
    else:
        reservations = [BookReservation(d) for d in db.book_reservations.find({"user_id": user_id}).sort("reservation_date", -1)]

    return render_template('reservations.html', reservations=reservations)

@booking_bp.route('/reservations/book/<book_id>', methods=['POST'])
@login_required
def reserve_book(book_id):
    db = get_db(current_app.config)
    book = Book.get_by_id(db, book_id)
    if not book:
        flash('Book not found.', 'danger')
        return redirect(url_for('books.catalog'))

    notes = request.form.get('notes', '')
    res, err = BookReservation.create(db, current_user, book, notes=notes)

    if err:
        flash(err, 'warning')
    else:
        flash(f"Reservation placed for '{book.title}'. You will be notified once ready for pickup.", 'success')

    return redirect(request.referrer or url_for('booking.reservations_view'))

@booking_bp.route('/reservations/cancel/<reservation_id>', methods=['POST'])
@login_required
def cancel_reservation(reservation_id):
    db = get_db(current_app.config)
    oid = ObjectId(reservation_id) if ObjectId.is_valid(reservation_id) else reservation_id
    res_doc = db.book_reservations.find_one({"_id": oid})

    if not res_doc:
        flash('Reservation not found.', 'danger')
        return redirect(url_for('booking.reservations_view'))

    if not current_user.is_admin and str(res_doc.get('user_id')) != str(current_user.id):
        flash('Unauthorized to cancel this reservation.', 'danger')
        return redirect(url_for('booking.reservations_view'))

    db.book_reservations.update_one({"_id": oid}, {"$set": {"status": "cancelled", "cancelled_at": utc_now()}})
    log_activity(db, current_user.id, current_user.name, "CANCEL_RESERVATION", f"Cancelled reservation {reservation_id}")
    flash('Book reservation cancelled.', 'info')
    return redirect(request.referrer or url_for('booking.reservations_view'))

@booking_bp.route('/reservations/approve/<reservation_id>', methods=['POST'])
@login_required
def approve_reservation(reservation_id):
    if not current_user.is_admin and not current_user.is_staff:
        flash('Permission denied.', 'danger')
        return redirect(url_for('booking.reservations_view'))

    db = get_db(current_app.config)
    BookReservation.update_status(db, reservation_id, "approved", admin_user=current_user)
    flash('Reservation approved and user notified.', 'success')
    return redirect(request.referrer or url_for('booking.reservations_view'))

@booking_bp.route('/reservations/reject/<reservation_id>', methods=['POST'])
@login_required
def reject_reservation(reservation_id):
    if not current_user.is_admin and not current_user.is_staff:
        flash('Permission denied.', 'danger')
        return redirect(url_for('booking.reservations_view'))

    db = get_db(current_app.config)
    BookReservation.update_status(db, reservation_id, "rejected", admin_user=current_user)
    flash('Reservation rejected.', 'warning')
    return redirect(request.referrer or url_for('booking.reservations_view'))
