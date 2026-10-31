from datetime import datetime
from flask import Blueprint, render_template, request, redirect, url_for, flash, current_app
from flask_login import login_required, current_user
from bson import ObjectId
from models.database import get_db, log_activity
from models.book import Book
from models.loan import Loan

loans_bp = Blueprint('loans', __name__)

@loans_bp.route('/loans')
@login_required
def loans_view():
    db = get_db(current_app.config)
    status_filter = request.args.get('status', 'all')
    user_id = str(current_user.id)

    query = {}
    if not current_user.is_admin:
        query["user_id"] = user_id

    if status_filter != 'all':
        query["status"] = status_filter

    loans_docs = list(db.loans.find(query).sort("issue_date", -1))
    loans = [Loan(d) for d in loans_docs]

    # Pre-calculate active vs completed counts
    if current_user.is_admin:
        active_count = db.loans.count_documents({"status": "active"})
        pending_count = db.loans.count_documents({"status": "pending"})
        returned_count = db.loans.count_documents({"status": "returned"})
    else:
        active_count = db.loans.count_documents({"user_id": user_id, "status": "active"})
        pending_count = db.loans.count_documents({"user_id": user_id, "status": "pending"})
        returned_count = db.loans.count_documents({"user_id": user_id, "status": "returned"})

    return render_template(
        'loans.html',
        loans=loans,
        status_filter=status_filter,
        active_count=active_count,
        pending_count=pending_count,
        returned_count=returned_count
    )

@loans_bp.route('/loans/request/<book_id>', methods=['POST'])
@login_required
def request_loan(book_id):
    db = get_db(current_app.config)
    book = Book.get_by_id(db, book_id)
    if not book:
        flash('Book not found in library catalog.', 'danger')
        return redirect(url_for('books.catalog'))

    loan, err = Loan.request_loan(db, current_user, book, current_app.config)
    if err:
        flash(err, 'warning')
    else:
        flash(f"Loan requested for '{book.title}'. Waiting for librarian approval.", 'success')

    return redirect(request.referrer or url_for('loans.loans_view'))

@loans_bp.route('/loans/approve/<loan_id>', methods=['POST'])
@login_required
def approve_loan(loan_id):
    if not current_user.is_admin and not current_user.is_staff:
        flash('Unauthorized access: Librarian or Admin role required.', 'danger')
        return redirect(url_for('loans.loans_view'))

    db = get_db(current_app.config)
    success, err = Loan.approve_loan(db, loan_id, current_user)
    if success:
        flash('Loan approved! Book copy checked out to borrower.', 'success')
    else:
        flash(f'Cannot approve loan: {err}', 'danger')

    return redirect(request.referrer or url_for('admin.dashboard'))

@loans_bp.route('/loans/reject/<loan_id>', methods=['POST'])
@login_required
def reject_loan(loan_id):
    if not current_user.is_admin and not current_user.is_staff:
        flash('Unauthorized access: Librarian or Admin role required.', 'danger')
        return redirect(url_for('loans.loans_view'))

    db = get_db(current_app.config)
    reason = request.form.get('reason', 'Declined by library administrator.')
    success, err = Loan.reject_loan(db, loan_id, current_user, reason=reason)
    if success:
        flash('Loan request rejected.', 'info')
    else:
        flash(f'Error rejecting loan: {err}', 'danger')

    return redirect(request.referrer or url_for('admin.dashboard'))

@loans_bp.route('/loans/return/<loan_id>', methods=['POST'])
@login_required
def process_return(loan_id):
    if not current_user.is_admin and not current_user.is_staff:
        flash('Unauthorized access: Staff or Admin role required to check in returns.', 'danger')
        return redirect(url_for('loans.loans_view'))

    db = get_db(current_app.config)
    condition = request.form.get('condition', 'Good')
    fine_per_day = current_app.config.get('FINE_PER_DAY', 1.0)

    success, msg, fine_amount = Loan.process_return(db, loan_id, current_user, fine_per_day=fine_per_day, condition=condition)
    if success:
        if fine_amount > 0:
            flash(f"Book returned. Overdue fine assessed: ${fine_amount:.2f}", 'warning')
        else:
            flash("Book returned and checked back into inventory successfully.", 'success')
    else:
        flash(f"Return failed: {msg}", 'danger')

    return redirect(request.referrer or url_for('admin.dashboard'))

@loans_bp.route('/loans/renew/<loan_id>', methods=['POST'])
@login_required
def renew_loan(loan_id):
    db = get_db(current_app.config)
    success, err = Loan.renew_loan(db, loan_id, current_user, extension_days=7)
    if success:
        flash('Loan renewed successfully! Due date extended by 7 days.', 'success')
    else:
        flash(f'Could not renew loan: {err}', 'warning')

    return redirect(request.referrer or url_for('loans.loans_view'))
