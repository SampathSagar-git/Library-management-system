from datetime import datetime
from flask import Blueprint, render_template, redirect, url_for, flash, current_app
from flask_login import login_required, current_user
from models.database import get_db
from models.loan import Loan
from models.reservation import BookReservation, DeskReservation
from models.neo4j_models import neo4j_service

staff_bp = Blueprint('staff', __name__, url_prefix='/staff')

@staff_bp.before_request
@login_required
def check_staff_role():
    if current_user.role not in ['staff', 'admin']:
        flash('Access restricted to staff/faculty members.', 'warning')
        return redirect(url_for('student.dashboard'))

@staff_bp.route('/dashboard')
def dashboard():
    db = get_db(current_app.config)
    user_id = str(current_user.id)

    # 1. Active & Personal Loans
    loans_cursor = db.loans.find({"user_id": user_id}).sort("issue_date", -1)
    all_loans = [Loan(d) for d in loans_cursor]
    active_loans = [l for l in all_loans if l.status in ['active', 'overdue']]
    pending_loans = [l for l in all_loans if l.status == 'pending']
    returned_loans = [l for l in all_loans if l.status == 'returned']

    # 2. Book Reservations
    book_res_cursor = db.book_reservations.find({"user_id": user_id}).sort("reservation_date", -1)
    all_reservations = [BookReservation(d) for d in book_res_cursor]
    active_reservations = [r for r in all_reservations if r.status in ['pending', 'approved']]

    # 3. Desk Bookings (Focus on Faculty Suites / Study Pods)
    desk_res_cursor = db.desk_reservations.find({"user_id": user_id}).sort("created_at", -1)
    all_desk_bookings = [DeskReservation(d) for d in desk_res_cursor]
    active_desk_bookings = [d for d in all_desk_bookings if d.status == 'confirmed']

    # 4. Library Resource Overview (Quick stats for faculty)
    total_books = db.books.count_documents({})
    available_books = db.books.count_documents({"available_copies": {"$gt": 0}})
    total_desks = db.desks.count_documents({})
    faculty_desks = db.desks.count_documents({"zone": "Faculty & Research Suites"})

    # 5. Notifications
    notifs = list(db.notifications.find({"user_id": user_id}).sort("created_at", -1).limit(6))

    # 6. Graph Recommendations for Faculty/Staff
    graph_recs = neo4j_service.get_recommendations(user_id, role="staff", limit=4)
    enriched_recs = []
    for r in graph_recs:
        b_doc = db.books.find_one({"title": r.get('title')}) or db.books.find_one({"isbn": r.get('isbn')})
        if b_doc:
            rec_item = dict(b_doc)
            rec_item['_id'] = str(b_doc['_id'])
            rec_item['rec_reason'] = r.get('recommendation_reason', r.get('reason', 'Academic research recommendation'))
            rec_item['rec_score'] = r.get('score', 1)
            enriched_recs.append(rec_item)

    if not enriched_recs:
        sample_books = list(db.books.find({"available_copies": {"$gt": 0}}).limit(4))
        for b in sample_books:
            b['_id'] = str(b['_id'])
            b['rec_reason'] = "Academic Resource"
            b['rec_score'] = 1
            enriched_recs.append(b)

    return render_template(
        'staff_dashboard.html',
        active_loans=active_loans,
        pending_loans=pending_loans,
        returned_loans=returned_loans,
        active_reservations=active_reservations,
        all_reservations=all_reservations,
        active_desk_bookings=active_desk_bookings,
        all_desk_bookings=all_desk_bookings,
        total_books=total_books,
        available_books=available_books,
        total_desks=total_desks,
        faculty_desks=faculty_desks,
        notifications=notifs,
        recommendations=enriched_recs
    )
