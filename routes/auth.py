from flask import Blueprint, render_template, redirect, url_for, flash, request, current_app
from flask_login import login_user, logout_user, login_required, current_user
from models.user import User
from models.database import get_db, log_activity

auth_bp = Blueprint('auth', __name__)

@auth_bp.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect_user(current_user)

    if request.method == 'POST':
        email = request.form.get('email', '').strip()
        password = request.form.get('password', '')
        remember = bool(request.form.get('remember'))

        db = get_db(current_app.config)
        user = User.get_by_email(db, email)

        if not user or not user.check_password(password):
            flash('Invalid email address or password. Please try again.', 'danger')
            return render_template('login.html', email=email)

        if not user.is_active:
            flash('Your account has been suspended by administration. Please contact the library desk.', 'danger')
            return render_template('login.html', email=email)

        login_user(user, remember=remember)
        log_activity(db, user.id, user.name, "LOGIN", f"User logged in from {request.remote_addr}", request.remote_addr)
        flash(f'Welcome back, {user.name}!', 'success')

        next_page = request.args.get('next')
        if next_page and next_page.startswith('/'):
            return redirect(next_page)
        return redirect_user(user)

    return render_template('login.html')

@auth_bp.route('/register', methods=['GET', 'POST'])
def register():
    if current_user.is_authenticated:
        return redirect_user(current_user)

    db = get_db(current_app.config)
    categories = list(db.categories.find().sort("name", 1))

    if request.method == 'POST':
        name = request.form.get('name', '').strip()
        email = request.form.get('email', '').strip()
        password = request.form.get('password', '')
        confirm_password = request.form.get('confirm_password', '')
        role = request.form.get('role', 'student')
        department = request.form.get('department', 'Computer Science')
        student_id = request.form.get('student_id', '')
        staff_id = request.form.get('staff_id', '')
        phone = request.form.get('phone', '')
        interests = request.form.getlist('interests')

        if not name or not email or not password:
            flash('Please fill in all mandatory fields.', 'warning')
            return render_template('register.html', categories=categories)

        if password != confirm_password:
            flash('Passwords do not match. Please retype.', 'danger')
            return render_template('register.html', categories=categories)

        if len(password) < 6:
            flash('Password must be at least 6 characters long.', 'warning')
            return render_template('register.html', categories=categories)

        # Restrict admin self-registration
        if role not in ['student', 'staff']:
            role = 'student'

        user, error = User.create(
            db, name=name, email=email, password=password, role=role,
            department=department, student_id=student_id, staff_id=staff_id,
            phone=phone, interests=interests
        )

        if error:
            flash(error, 'danger')
            return render_template('register.html', categories=categories)

        login_user(user)
        log_activity(db, user.id, user.name, "REGISTER", f"Registered new account as {role}", request.remote_addr)
        flash('Registration successful! Welcome to the Smart Library.', 'success')
        return redirect_user(user)

    return render_template('register.html', categories=categories)

@auth_bp.route('/logout')
@login_required
def logout():
    db = get_db(current_app.config)
    log_activity(db, current_user.id, current_user.name, "LOGOUT", "User logged out", request.remote_addr)
    logout_user()
    flash('You have been logged out successfully.', 'info')
    return redirect(url_for('auth.login'))

def redirect_user(user):
    if user.role == 'admin':
        return redirect(url_for('admin.dashboard'))
    elif user.role == 'staff':
        return redirect(url_for('staff.dashboard'))
    else:
        return redirect(url_for('student.dashboard'))
