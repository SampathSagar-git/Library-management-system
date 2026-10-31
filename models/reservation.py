from datetime import datetime, timedelta, timezone
from bson import ObjectId
from models.neo4j_models import neo4j_service
from models.database import create_notification, log_activity, utc_now

class BookReservation:
    def __init__(self, data):
        self.data = data
        self.id = str(data.get('_id'))
        self.user_id = str(data.get('user_id'))
        self.user_name = data.get('user_name', '')
        self.user_email = data.get('user_email', '')
        self.user_role = data.get('user_role', 'student')
        self.book_id = str(data.get('book_id'))
        self.book_title = data.get('book_title', '')
        self.book_author = data.get('book_author', '')
        self.book_cover = data.get('book_cover', '')
        self.status = data.get('status', 'pending') # 'pending', 'approved', 'fulfilled', 'cancelled', 'rejected'
        self.reservation_date = data.get('reservation_date', utc_now())
        self.expiry_date = data.get('expiry_date')
        self.notes = data.get('notes', '')

    @staticmethod
    def create(db, user, book, notes=""):
        # Check if already reserved by this user and active
        existing = db.book_reservations.find_one({
            "user_id": str(user.id),
            "book_id": str(book.id),
            "status": {"$in": ["pending", "approved"]}
        })
        if existing:
            return None, "You already have an active reservation for this book."

        # Active loans check: if user already has this book borrowed
        has_loan = db.loans.find_one({
            "user_id": str(user.id),
            "book_id": str(book.id),
            "status": {"$in": ["active", "pending"]}
        })
        if has_loan:
            return None, "You currently have a loan or pending loan for this book."

        expiry = utc_now() + timedelta(days=7)
        res_doc = {
            "user_id": str(user.id),
            "user_name": user.name,
            "user_email": user.email,
            "user_role": user.role,
            "book_id": str(book.id),
            "book_title": book.title,
            "book_author": book.author,
            "book_cover": book.cover_image,
            "status": "pending",
            "reservation_date": utc_now(),
            "expiry_date": expiry,
            "notes": notes.strip()
        }
        res = db.book_reservations.insert_one(res_doc)
        res_doc['_id'] = res.inserted_id

        # Record in Neo4j
        try:
            neo4j_service.record_reservation(user.id, book.id, user.role)
        except Exception:
            pass

        # Create user notification
        create_notification(
            db, user.id, 
            "Book Reservation Received", 
            f"Your reservation for '{book.title}' is pending approval by the library staff.",
            "info"
        )
        log_activity(db, user.id, user.name, "RESERVED_BOOK", f"Reserved book '{book.title}' (ID: {book.id})")

        return BookReservation(res_doc), None

    @staticmethod
    def update_status(db, reservation_id, new_status, admin_user=None):
        oid = ObjectId(reservation_id) if ObjectId.is_valid(reservation_id) else reservation_id
        res_doc = db.book_reservations.find_one({"_id": oid})
        if not res_doc:
            return False, "Reservation not found."

        db.book_reservations.update_one(
            {"_id": oid},
            {"$set": {"status": new_status, "updated_at": utc_now()}}
        )

        user_id = res_doc.get('user_id')
        book_title = res_doc.get('book_title')
        notif_msg = f"Your reservation for '{book_title}' has been {new_status}."
        notif_type = "success" if new_status == "approved" else ("danger" if new_status == "rejected" else "info")
        create_notification(db, user_id, f"Reservation {new_status.capitalize()}", notif_msg, notif_type)

        if admin_user:
            log_activity(db, admin_user.id, admin_user.name, "UPDATE_RESERVATION", f"Updated reservation {reservation_id} for '{book_title}' to {new_status}")

        return True, None


class DeskReservation:
    def __init__(self, data):
        self.data = data
        self.id = str(data.get('_id'))
        self.desk_id = str(data.get('desk_id', ''))
        self.desk_number = data.get('desk_number', '')
        self.zone = data.get('zone', 'Quiet Study Pods')
        self.user_id = str(data.get('user_id'))
        self.user_name = data.get('user_name', '')
        self.user_email = data.get('user_email', '')
        self.user_role = data.get('user_role', 'student')
        self.booking_date = data.get('booking_date', '') # YYYY-MM-DD
        self.start_time = data.get('start_time', '')     # HH:MM
        self.end_time = data.get('end_time', '')         # HH:MM
        self.duration_hours = int(data.get('duration_hours', 2))
        self.purpose = data.get('purpose', 'Individual Study')
        self.status = data.get('status', 'confirmed')    # 'confirmed', 'cancelled', 'completed'
        self.created_at = data.get('created_at', utc_now())

    @staticmethod
    def parse_time_minutes(t_str):
        parts = t_str.split(":")
        return int(parts[0]) * 60 + int(parts[1])

    @staticmethod
    def check_collision(db, desk_number, booking_date, start_time, end_time, exclude_id=None):
        """
        Prevents double-booking: returns True if another confirmed booking overlaps.
        """
        query = {
            "desk_number": desk_number,
            "booking_date": booking_date,
            "status": "confirmed"
        }
        if exclude_id:
            query["_id"] = {"$ne": ObjectId(exclude_id) if ObjectId.is_valid(exclude_id) else exclude_id}

        existing_bookings = list(db.desk_reservations.find(query))
        new_start = DeskReservation.parse_time_minutes(start_time)
        new_end = DeskReservation.parse_time_minutes(end_time)

        for b in existing_bookings:
            b_start = DeskReservation.parse_time_minutes(b.get('start_time', '00:00'))
            b_end = DeskReservation.parse_time_minutes(b.get('end_time', '00:00'))
            # Overlap condition: max(start1, start2) < min(end1, end2)
            if max(new_start, b_start) < min(new_end, b_end):
                return True, b
        return False, None

    @staticmethod
    def create(db, user, desk_number, zone, booking_date, start_time, duration_hours=2, purpose="Study"):
        # Calculate end_time
        start_min = DeskReservation.parse_time_minutes(start_time)
        end_min = start_min + (duration_hours * 60)
        end_time = f"{end_min // 60:02d}:{end_min % 60:02d}"

        # Collision verification
        collision, existing = DeskReservation.check_collision(db, desk_number, booking_date, start_time, end_time)
        if collision:
            return None, f"Desk {desk_number} is already booked on {booking_date} from {existing.get('start_time')} to {existing.get('end_time')}."

        # Check user's bookings on the same date (limit 1 desk per time slot)
        user_overlap = db.desk_reservations.find_one({
            "user_id": str(user.id),
            "booking_date": booking_date,
            "status": "confirmed"
        })
        if user_overlap:
            u_start = DeskReservation.parse_time_minutes(user_overlap.get('start_time', '00:00'))
            u_end = DeskReservation.parse_time_minutes(user_overlap.get('end_time', '00:00'))
            if max(start_min, u_start) < min(end_min, u_end):
                return None, f"You already have a reserved desk ({user_overlap.get('desk_number')}) during this time window."

        booking_doc = {
            "desk_number": desk_number,
            "zone": zone,
            "user_id": str(user.id),
            "user_name": user.name,
            "user_email": user.email,
            "user_role": user.role,
            "booking_date": booking_date,
            "start_time": start_time,
            "end_time": end_time,
            "duration_hours": duration_hours,
            "purpose": purpose.strip() or "Self Study",
            "status": "confirmed",
            "created_at": utc_now()
        }

        result = db.desk_reservations.insert_one(booking_doc)
        booking_doc['_id'] = result.inserted_id

        # Neo4j Graph edge
        try:
            neo4j_service.sync_desk(desk_number, zone)
            neo4j_service.record_desk_booking(user.id, desk_number, user.role, booking_date, start_time)
        except Exception:
            pass

        create_notification(
            db, user.id,
            "Desk Booking Confirmed",
            f"You have booked Desk {desk_number} ({zone}) for {booking_date} at {start_time}-{end_time}.",
            "success"
        )
        log_activity(db, user.id, user.name, "BOOKED_DESK", f"Booked Desk {desk_number} on {booking_date} ({start_time}-{end_time})")

        return DeskReservation(booking_doc), None

    @staticmethod
    def cancel(db, booking_id, user):
        oid = ObjectId(booking_id) if ObjectId.is_valid(booking_id) else booking_id
        booking = db.desk_reservations.find_one({"_id": oid})
        if not booking:
            return False, "Booking not found."

        if not user.is_admin and str(booking.get('user_id')) != str(user.id):
            return False, "Unauthorized to cancel this booking."

        db.desk_reservations.update_one({"_id": oid}, {"$set": {"status": "cancelled", "cancelled_at": utc_now()}})
        
        create_notification(
            db, booking.get('user_id'),
            "Desk Booking Cancelled",
            f"Your booking for Desk {booking.get('desk_number')} on {booking.get('booking_date')} was cancelled.",
            "warning"
        )
        log_activity(db, user.id, user.name, "CANCELLED_DESK", f"Cancelled Desk {booking.get('desk_number')} booking {booking_id}")
        return True, None
