from datetime import datetime
from flask import Blueprint, render_template, redirect, url_for, flash, current_app
from flask_login import login_required, current_user
from models.database import get_db
from models.loan import Loan
from models.reservation import BookReservation, DeskReservation
from models.neo4j_models import neo4j_service

student_bp = Blueprint('student', __name__, url_prefix='/student')

@student_bp.before_request
@login_required
def check_student_role():
    if current_user.role not in ['student', 'admin']:
        flash('Access restricted to students.', 'warning')
        return redirect(url_for('staff.dashboard'))

@student_bp.route('/dashboard')
def dashboard():
    db = get_db(current_app.config)
    user_id = str(current_user.id)

    # 1. Active & Overdue Loans
    loans_cursor = db.loans.find({"user_id": user_id}).sort("issue_date", -1)
    all_loans = [Loan(d) for d in loans_cursor]
    active_loans = [l for l in all_loans if l.status in ['active', 'overdue']]
    pending_loans = [l for l in all_loans if l.status == 'pending']
    returned_loans = [l for l in all_loans if l.status == 'returned']

    # 2. Book Reservations
    book_res_cursor = db.book_reservations.find({"user_id": user_id}).sort("reservation_date", -1)
    book_reservations = [BookReservation(d) for d in book_res_cursor]
    active_reservations = [r for r in book_reservations if r.status in ['pending', 'approved']]

    # 3. Desk Reservations
    desk_res_cursor = db.desk_reservations.find({"user_id": user_id}).sort("created_at", -1)
    all_desk_bookings = [DeskReservation(d) for d in desk_res_cursor]
    active_desk_bookings = [d for d in all_desk_bookings if d.status == 'confirmed']

    # 4. Fines
    fines_cursor = db.fines.find({"user_id": user_id, "status": "unpaid"})
    unpaid_fines = list(fines_cursor)
    total_fine_amount = sum(f.get('amount', 0.0) for f in unpaid_fines)

    # 5. Notifications
    notifs = list(db.notifications.find({"user_id": user_id}).sort("created_at", -1).limit(6))

    # 6. Neo4j Graph Recommendations
    graph_recs = neo4j_service.get_recommendations(user_id, role="student", limit=4)
    # Enrich graph recs with book details from Mongo
    enriched_recs = []
    for r in graph_recs:
        b_doc = db.books.find_one({"title": r.get('title')}) or db.books.find_one({"isbn": r.get('isbn')})
        if b_doc:
            rec_item = dict(b_doc)
            rec_item['_id'] = str(b_doc['_id'])
            rec_item['rec_reason'] = r.get('recommendation_reason', r.get('reason', 'Curated for your profile'))
            rec_item['rec_score'] = r.get('score', 1)
            enriched_recs.append(rec_item)

    # Fallback if recommendations empty (e.g. brand new user)
    if not enriched_recs:
        sample_books = list(db.books.find({"available_copies": {"$gt": 0}}).limit(4))
        for b in sample_books:
            b['_id'] = str(b['_id'])
            b['rec_reason'] = "Featured Campus Reading"
            b['rec_score'] = 1
            enriched_recs.append(b)

    return render_template(
        'student_dashboard.html',
        active_loans=active_loans,
        pending_loans=pending_loans,
        returned_loans=returned_loans,
        active_reservations=active_reservations,
        all_reservations=book_reservations,
        active_desk_bookings=active_desk_bookings,
        all_desk_bookings=all_desk_bookings,
        unpaid_fines=unpaid_fines,
        total_fine_amount=total_fine_amount,
        notifications=notifs,
        recommendations=enriched_recs
    )
