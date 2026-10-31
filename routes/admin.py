from datetime import datetime, timedelta
from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify, current_app
from flask_login import login_required, current_user
from bson import ObjectId
from models.database import get_db, log_activity, create_notification, utc_now
from models.user import User
from models.book import Book
from models.loan import Loan
from models.reservation import BookReservation, DeskReservation
from models.neo4j_models import neo4j_service

admin_bp = Blueprint('admin', __name__, url_prefix='/admin')

@admin_bp.before_request
@login_required
def check_admin_role():
    if not current_user.is_admin:
        flash('Access restricted to Library Administrators.', 'danger')
        return redirect(url_for('auth.login'))

@admin_bp.route('/dashboard')
def dashboard():
    db = get_db(current_app.config)

    # 1. High-Level Metrics
    total_books = db.books.count_documents({})
    # Total physical copies
    pipeline_copies = [{"$group": {"_id": None, "total": {"$sum": "$quantity"}, "avail": {"$sum": "$available_copies"}}}]
    copies_agg = list(db.books.aggregate(pipeline_copies))
    total_copies = copies_agg[0]['total'] if copies_agg else 0
    available_copies = copies_agg[0]['avail'] if copies_agg else 0
    borrowed_copies = total_copies - available_copies

    registered_students = db.users.count_documents({"role": "student"})
    registered_staff = db.users.count_documents({"role": "staff"})
    
    total_desks = db.desks.count_documents({})
    today_str = utc_now().strftime('%Y-%m-%d')
    active_desk_bookings_today = db.desk_reservations.count_documents({"booking_date": today_str, "status": "confirmed"})
    available_desks = max(0, total_desks - active_desk_bookings_today)

    active_reservations = db.book_reservations.count_documents({"status": {"$in": ["pending", "approved"]}})
    pending_loan_requests = db.loans.count_documents({"status": "pending"})
    
    # Overdue loans
    now = utc_now()
    overdue_loans_count = db.loans.count_documents({
        "status": "active",
        "due_date": {"$lt": now}
    })

    # Unpaid fines
    pipeline_fines = [{"$match": {"status": "unpaid"}}, {"$group": {"_id": None, "total": {"$sum": "$amount"}}}]
    fines_agg = list(db.fines.aggregate(pipeline_fines))
    total_unpaid_fines = fines_agg[0]['total'] if fines_agg else 0.0

    # 2. Lists for management tabs
    books_list = [Book(d) for d in db.books.find().sort("created_at", -1).limit(50)]
    categories_list = list(db.categories.find().sort("name", 1))
    
    pending_loans = [Loan(d) for d in db.loans.find({"status": "pending"}).sort("created_at", -1)]
    active_loans = [Loan(d) for d in db.loans.find({"status": {"$in": ["active", "overdue"]}}).sort("due_date", 1)]
    
    pending_reservations = [BookReservation(d) for d in db.book_reservations.find({"status": "pending"}).sort("reservation_date", -1)]
    all_reservations = [BookReservation(d) for d in db.book_reservations.find().sort("reservation_date", -1).limit(30)]

    desks_list = list(db.desks.find().sort("desk_number", 1))
    desk_bookings_today = [DeskReservation(d) for d in db.desk_reservations.find({"booking_date": today_str}).sort("start_time", 1)]

    users_list = User.get_all(db)
    unpaid_fines_list = list(db.fines.find({"status": "unpaid"}).sort("created_at", -1))
    activity_logs = list(db.activity_logs.find().sort("timestamp", -1).limit(25))

    # Graph statistics
    graph_stats = neo4j_service.get_graph_stats()

    stats = {
        'total_books': total_books,
        'total_copies': total_copies,
        'available_copies': available_copies,
        'borrowed_copies': borrowed_copies,
        'registered_students': registered_students,
        'registered_staff': registered_staff,
        'total_users': registered_students + registered_staff,
        'total_desks': total_desks,
        'available_desks': available_desks,
        'active_reservations': active_reservations,
        'pending_loan_requests': pending_loan_requests,
        'overdue_loans_count': overdue_loans_count,
        'total_unpaid_fines': total_unpaid_fines,
        'graph_nodes': graph_stats.get('total_nodes', 0),
        'graph_relationships': graph_stats.get('total_relationships', 0)
    }

    return render_template(
        'admin_dashboard.html',
        stats=stats,
        books=books_list,
        categories=categories_list,
        pending_loans=pending_loans,
        active_loans=active_loans,
        pending_reservations=pending_reservations,
        all_reservations=all_reservations,
        desks=desks_list,
        desk_bookings_today=desk_bookings_today,
        users=users_list,
        fines=unpaid_fines_list,
        activity_logs=activity_logs,
        graph_stats=graph_stats
    )

# ================= Chart.js Analytics API =================

@admin_bp.route('/api/analytics')
def get_analytics():
    db = get_db(current_app.config)

    # 1. Borrowing trends (last 7 days)
    today = utc_now().date()
    days_labels = []
    loan_counts = []
    return_counts = []

    for i in range(6, -1, -1):
        d = today - timedelta(days=i)
        start_d = datetime(d.year, d.month, d.day, 0, 0, 0)
        end_d = datetime(d.year, d.month, d.day, 23, 59, 59)
        days_labels.append(d.strftime('%a, %b %d'))

        l_cnt = db.loans.count_documents({"created_at": {"$gte": start_d, "$lte": end_d}})
        r_cnt = db.returns.count_documents({"return_date": {"$gte": start_d, "$lte": end_d}})
        loan_counts.append(l_cnt)
        return_counts.append(r_cnt)

    # 2. Books by Category
    pipeline_cat = [
        {"$group": {"_id": "$category", "count": {"$sum": 1}}},
        {"$sort": {"count": -1}},
        {"$limit": 7}
    ]
    cat_agg = list(db.books.aggregate(pipeline_cat))
    cat_labels = [c['_id'] or 'General' for c in cat_agg]
    cat_counts = [c['count'] for c in cat_agg]

    # 3. Desk Occupancy by Zone
    today_str = utc_now().strftime('%Y-%m-%d')
    pipeline_zones = [
        {"$match": {"booking_date": today_str, "status": "confirmed"}},
        {"$group": {"_id": "$zone", "count": {"$sum": 1}}}
    ]
    zone_agg = list(db.desk_reservations.aggregate(pipeline_zones))
    zone_dict = {z['_id']: z['count'] for z in zone_agg}
    all_zones = ["Quiet Study Pods", "Collaborative Zone", "Tech & Media Lab", "Faculty & Research Suites"]
    zone_labels = all_zones
    zone_counts = [zone_dict.get(z, 0) for z in all_zones]

    # 4. Neo4j Graph Data
    graph_vis = neo4j_service.get_graph_visualization(limit=30)

    return jsonify({
        "trends": {
            "labels": days_labels,
            "loans": loan_counts,
            "returns": return_counts
        },
        "categories": {
            "labels": cat_labels,
            "counts": cat_counts
        },
        "desks": {
            "labels": zone_labels,
            "counts": zone_counts
        },
        "graph": graph_vis
    })

# ================= User Management =================

@admin_bp.route('/users/toggle-status/<user_id>', methods=['POST'])
def toggle_user_status(user_id):
    db = get_db(current_app.config)
    oid = ObjectId(user_id) if ObjectId.is_valid(user_id) else user_id
    user_doc = db.users.find_one({"_id": oid})
    if not user_doc:
        flash('User not found.', 'danger')
        return redirect(url_for('admin.dashboard'))

    new_status = 'suspended' if user_doc.get('status') == 'active' else 'active'
    db.users.update_one({"_id": oid}, {"$set": {"status": new_status}})
    log_activity(db, current_user.id, current_user.name, "USER_STATUS_CHANGE", f"Changed status of {user_doc.get('email')} to {new_status}")
    flash(f"User {user_doc.get('name')} status changed to {new_status}.", 'info')
    return redirect(url_for('admin.dashboard'))

@admin_bp.route('/users/change-role/<user_id>', methods=['POST'])
def change_user_role(user_id):
    db = get_db(current_app.config)
    new_role = request.form.get('role', 'student')
    if new_role not in ['student', 'staff', 'admin']:
        flash('Invalid role specified.', 'warning')
        return redirect(url_for('admin.dashboard'))

    oid = ObjectId(user_id) if ObjectId.is_valid(user_id) else user_id
    db.users.update_one({"_id": oid}, {"$set": {"role": new_role}})
    log_activity(db, current_user.id, current_user.name, "USER_ROLE_CHANGE", f"Updated user {user_id} role to {new_role}")
    flash('User role updated successfully.', 'success')
    return redirect(url_for('admin.dashboard'))

# ================= Fine Actions =================

@admin_bp.route('/fines/pay/<fine_id>', methods=['POST'])
def mark_fine_paid(fine_id):
    db = get_db(current_app.config)
    oid = ObjectId(fine_id) if ObjectId.is_valid(fine_id) else fine_id
    db.fines.update_one({"_id": oid}, {"$set": {"status": "paid", "paid_at": utc_now(), "handled_by": current_user.name}})
    flash('Fine marked as paid.', 'success')
    return redirect(url_for('admin.dashboard'))

@admin_bp.route('/fines/waive/<fine_id>', methods=['POST'])
def waive_fine(fine_id):
    db = get_db(current_app.config)
    oid = ObjectId(fine_id) if ObjectId.is_valid(fine_id) else fine_id
    db.fines.update_one({"_id": oid}, {"$set": {"status": "waived", "waived_at": utc_now(), "waived_by": current_user.name}})
    flash('Fine waived successfully.', 'info')
    return redirect(url_for('admin.dashboard'))

# ================= Category Management =================

@admin_bp.route('/categories/add', methods=['POST'])
def add_category():
    db = get_db(current_app.config)
    name = request.form.get('name', '').strip()
    description = request.form.get('description', '').strip()
    color = request.form.get('color_code', '#2563eb').strip()

    if not name:
        flash('Category name is required.', 'warning')
        return redirect(url_for('admin.dashboard'))

    db.categories.update_one(
        {"name": name},
        {"$setOnInsert": {"name": name, "description": description, "color_code": color, "book_count": 0}},
        upsert=True
    )
    flash(f"Category '{name}' saved successfully.", 'success')
    return redirect(url_for('admin.dashboard'))
