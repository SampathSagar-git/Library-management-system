from datetime import datetime, timedelta, timezone
from bson import ObjectId
from models.neo4j_models import neo4j_service
from models.database import create_notification, log_activity, utc_now

class Loan:
    def __init__(self, data):
        self.data = data
        self.id = str(data.get('_id'))
        self.book_id = str(data.get('book_id'))
        self.book_title = data.get('book_title', '')
        self.book_author = data.get('book_author', '')
        self.book_cover = data.get('book_cover', '')
        self.book_isbn = data.get('book_isbn', '')
        self.user_id = str(data.get('user_id'))
        self.user_name = data.get('user_name', '')
        self.user_email = data.get('user_email', '')
        self.user_role = data.get('user_role', 'student')
        self.issue_date = data.get('issue_date', utc_now())
        self.due_date = data.get('due_date')
        self.return_date = data.get('return_date')
        self.status = data.get('status', 'pending') # 'pending', 'active', 'returned', 'overdue', 'rejected'
        self.renew_count = int(data.get('renew_count', 0))
        self.fine_amount = float(data.get('fine_amount', 0.0))
        self.fine_status = data.get('fine_status', 'none') # 'none', 'unpaid', 'paid', 'waived'
        self.notes = data.get('notes', '')

    @property
    def is_overdue(self):
        if self.status == 'active' and self.due_date and utc_now() > self.due_date:
            return True
        return self.status == 'overdue'

    @property
    def overdue_days(self):
        if not self.due_date:
            return 0
        ref_date = self.return_date if self.return_date else utc_now()
        if ref_date > self.due_date:
            return (ref_date - self.due_date).days
        return 0

    @staticmethod
    def calculate_fine(due_date, return_date=None, fine_per_day=1.0):
        if not due_date:
            return 0.0
        ref = return_date if return_date else utc_now()
        if ref > due_date:
            days = (ref - due_date).days
            return round(max(0, days) * fine_per_day, 2)
        return 0.0

    @staticmethod
    def _cfg_val(config, key, default):
        if not config:
            return default
        if hasattr(config, 'get'):
            return config.get(key, default)
        return getattr(config, key, default)

    @staticmethod
    def request_loan(db, user, book, config=None):
        # 1. Check max active loans limit
        staff_max = Loan._cfg_val(config, 'STAFF_MAX_LOANS', 10)
        student_max = Loan._cfg_val(config, 'STUDENT_MAX_LOANS', 5)
        max_allowed = staff_max if user.role == 'staff' else student_max
        current_loans = db.loans.count_documents({
            "user_id": str(user.id),
            "status": {"$in": ["active", "pending", "overdue"]}
        })
        if current_loans >= max_allowed:
            return None, f"You have reached your maximum borrowing quota ({max_allowed} books)."

        # 2. Check if user already has an active loan for this book
        existing = db.loans.find_one({
            "user_id": str(user.id),
            "book_id": str(book.id),
            "status": {"$in": ["active", "pending", "overdue"]}
        })
        if existing:
            return None, "You already have a loan or pending loan request for this book."

        # 3. Check book copy availability
        book_doc = db.books.find_one({"_id": ObjectId(book.id) if ObjectId.is_valid(book.id) else book.id})
        if not book_doc or book_doc.get('available_copies', 0) <= 0:
            return None, "No copies of this book are currently available to borrow. You can place a reservation instead."

        staff_days = Loan._cfg_val(config, 'STAFF_LOAN_DAYS', 30)
        student_days = Loan._cfg_val(config, 'STUDENT_LOAN_DAYS', 14)
        loan_days = staff_days if user.role == 'staff' else student_days
        issue_date = utc_now()
        due_date = issue_date + timedelta(days=loan_days)

        loan_doc = {
            "book_id": str(book.id),
            "book_title": book.title,
            "book_author": book.author,
            "book_cover": book.cover_image,
            "book_isbn": book.isbn,
            "user_id": str(user.id),
            "user_name": user.name,
            "user_email": user.email,
            "user_role": user.role,
            "issue_date": issue_date,
            "due_date": due_date,
            "return_date": None,
            "status": "pending",
            "renew_count": 0,
            "fine_amount": 0.0,
            "fine_status": "none",
            "created_at": utc_now()
        }

        res = db.loans.insert_one(loan_doc)
        loan_doc['_id'] = res.inserted_id

        create_notification(
            db, user.id,
            "Borrow Request Submitted",
            f"Your request to borrow '{book.title}' has been submitted and awaits librarian approval.",
            "info"
        )
        log_activity(db, user.id, user.name, "REQUEST_LOAN", f"Requested loan for '{book.title}' (ISBN: {book.isbn})")

        return Loan(loan_doc), None

    @staticmethod
    def approve_loan(db, loan_id, admin_user):
        oid = ObjectId(loan_id) if ObjectId.is_valid(loan_id) else loan_id
        loan_doc = db.loans.find_one({"_id": oid})
        if not loan_doc:
            return False, "Loan request not found."

        book_id = loan_doc.get('book_id')
        b_oid = ObjectId(book_id) if ObjectId.is_valid(book_id) else book_id
        book_doc = db.books.find_one({"_id": b_oid})

        if not book_doc or book_doc.get('available_copies', 0) <= 0:
            return False, "Cannot approve: no copies available in inventory."

        # Decrement available copies
        db.books.update_one({"_id": b_oid}, {"$inc": {"available_copies": -1}})

        # Update loan to active
        now = utc_now()
        role = loan_doc.get('user_role', 'student')
        days = 30 if role == 'staff' else 14
        due = now + timedelta(days=days)

        db.loans.update_one(
            {"_id": oid},
            {"$set": {"status": "active", "issue_date": now, "due_date": due, "approved_by": admin_user.name}}
        )

        # Fulfill any pending reservations for this book & user
        db.book_reservations.update_one(
            {"user_id": loan_doc.get('user_id'), "book_id": book_id, "status": "pending"},
            {"$set": {"status": "fulfilled", "fulfilled_at": now}}
        )

        # Sync to Neo4j graph: User BORROWED Book!
        try:
            neo4j_service.record_borrow(loan_doc.get('user_id'), book_id, role, loan_id=str(oid))
        except Exception:
            pass

        create_notification(
            db, loan_doc.get('user_id'),
            "Book Loan Approved!",
            f"Your loan for '{loan_doc.get('book_title')}' has been approved. Due date: {due.strftime('%Y-%m-%d')}.",
            "success"
        )
        log_activity(db, admin_user.id, admin_user.name, "APPROVE_LOAN", f"Approved loan {loan_id} for '{loan_doc.get('book_title')}'")

        return True, None

    @staticmethod
    def reject_loan(db, loan_id, admin_user, reason="Loan request declined by library admin."):
        oid = ObjectId(loan_id) if ObjectId.is_valid(loan_id) else loan_id
        loan_doc = db.loans.find_one({"_id": oid})
        if not loan_doc:
            return False, "Loan request not found."

        db.loans.update_one({"_id": oid}, {"$set": {"status": "rejected", "rejection_reason": reason}})

        create_notification(
            db, loan_doc.get('user_id'),
            "Borrow Request Declined",
            f"Your request for '{loan_doc.get('book_title')}' was declined. Reason: {reason}",
            "danger"
        )
        log_activity(db, admin_user.id, admin_user.name, "REJECT_LOAN", f"Declined loan {loan_id} for '{loan_doc.get('book_title')}'")
        return True, None

    @staticmethod
    def process_return(db, loan_id, admin_user, fine_per_day=1.0, condition="Good"):
        oid = ObjectId(loan_id) if ObjectId.is_valid(loan_id) else loan_id
        loan_doc = db.loans.find_one({"_id": oid})
        if not loan_doc or loan_doc.get('status') not in ['active', 'overdue']:
            return False, "Active loan not found.", 0.0

        now = utc_now()
        due_date = loan_doc.get('due_date')
        fine_amount = Loan.calculate_fine(due_date, now, fine_per_day)
        fine_status = "unpaid" if fine_amount > 0 else "none"

        # Update loan record
        db.loans.update_one(
            {"_id": oid},
            {"$set": {
                "status": "returned",
                "return_date": now,
                "fine_amount": fine_amount,
                "fine_status": fine_status,
                "returned_by_admin": admin_user.name
            }}
        )

        # Restore available copies in inventory
        book_id = loan_doc.get('book_id')
        b_oid = ObjectId(book_id) if ObjectId.is_valid(book_id) else book_id
        db.books.update_one({"_id": b_oid}, {"$inc": {"available_copies": 1}})

        # Record in returns collection
        db.returns.insert_one({
            "loan_id": str(oid),
            "book_id": book_id,
            "book_title": loan_doc.get('book_title'),
            "user_id": loan_doc.get('user_id'),
            "user_name": loan_doc.get('user_name'),
            "return_date": now,
            "condition": condition,
            "fine_assessed": fine_amount,
            "processed_by": admin_user.name
        })

        # Record fine if applicable
        if fine_amount > 0:
            db.fines.insert_one({
                "loan_id": str(oid),
                "user_id": loan_doc.get('user_id'),
                "user_name": loan_doc.get('user_name'),
                "book_title": loan_doc.get('book_title'),
                "amount": fine_amount,
                "reason": f"Overdue return ({Loan(loan_doc).overdue_days} days)",
                "status": "unpaid",
                "created_at": now
            })

        create_notification(
            db, loan_doc.get('user_id'),
            "Book Return Processed",
            f"Return for '{loan_doc.get('book_title')}' processed successfully." + (f" Outstanding fine: ${fine_amount:.2f}." if fine_amount > 0 else ""),
            "info" if fine_amount == 0 else "warning"
        )
        log_activity(db, admin_user.id, admin_user.name, "PROCESS_RETURN", f"Processed return for loan {loan_id}. Fine assessed: ${fine_amount:.2f}")

        return True, "Return processed successfully.", fine_amount

    @staticmethod
    def renew_loan(db, loan_id, user, extension_days=7):
        oid = ObjectId(loan_id) if ObjectId.is_valid(loan_id) else loan_id
        loan_doc = db.loans.find_one({"_id": oid})
        if not loan_doc or loan_doc.get('status') != 'active':
            return False, "Only active loans can be renewed."

        if not user.is_admin and str(loan_doc.get('user_id')) != str(user.id):
            return False, "Unauthorized to renew this loan."

        if loan_doc.get('renew_count', 0) >= 2:
            return False, "Maximum renewal limit (2 times) reached for this loan."

        # Check if another user has reserved this book
        pending_res = db.book_reservations.find_one({
            "book_id": loan_doc.get('book_id'),
            "status": "pending"
        })
        if pending_res:
            return False, "Cannot renew: another student/staff member has reserved this book."

        curr_due = loan_doc.get('due_date', utc_now())
        new_due = curr_due + timedelta(days=extension_days)

        db.loans.update_one(
            {"_id": oid},
            {
                "$set": {"due_date": new_due},
                "$inc": {"renew_count": 1}
            }
        )

        create_notification(
            db, loan_doc.get('user_id'),
            "Loan Renewed Successfully",
            f"Your loan for '{loan_doc.get('book_title')}' has been extended to {new_due.strftime('%Y-%m-%d')}.",
            "success"
        )
        log_activity(db, user.id, user.name, "RENEW_LOAN", f"Renewed loan {loan_id} until {new_due.strftime('%Y-%m-%d')}")
        return True, None
