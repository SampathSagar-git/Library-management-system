import os
from datetime import datetime
from flask import Flask, render_template, request, redirect, url_for, flash
from flask_login import LoginManager, current_user
from config import Config
from models.database import get_db, is_mongo_mock, utc_now
from models.user import User
from models.book import Book
from models.neo4j_models import neo4j_service
from routes.auth import auth_bp
from routes.student import student_bp
from routes.staff import staff_bp
from routes.admin import admin_bp
from routes.books import books_bp
from routes.booking import booking_bp
from routes.loans import loans_bp
from seed_data import seed_database

def create_app():
    app = Flask(__name__)
    app.config.from_object(Config)

    # Initialize Flask-Login
    login_manager = LoginManager()
    login_manager.login_view = 'auth.login'
    login_manager.login_message = 'Please log in to access this library service.'
    login_manager.login_message_category = 'warning'
    login_manager.init_app(app)

    @login_manager.user_loader
    def load_user(user_id):
        db = get_db(app.config)
        return User.get_by_id(db, user_id)

    # Register Route Blueprints
    app.register_blueprint(auth_bp)
    app.register_blueprint(student_bp)
    app.register_blueprint(staff_bp)
    app.register_blueprint(admin_bp)
    app.register_blueprint(books_bp)
    app.register_blueprint(booking_bp)
    app.register_blueprint(loans_bp)

    # Global Context Processors
    @app.context_processor
    def inject_global_data():
        db = get_db(app.config)
        unread_notifications = 0
        if current_user.is_authenticated:
            unread_notifications = db.notifications.count_documents({
                "user_id": str(current_user.id),
                "is_read": False
            })

        return {
            'now_year': utc_now().year,
            'unread_notifications_count': unread_notifications,
            'is_mongo_mock': is_mongo_mock(),
            'is_neo4j_live': neo4j_service.is_live
        }

    # Homepage Route
    @app.route('/')
    def index():
        db = get_db(app.config)

        # Quick stats for hero banner
        total_books = db.books.count_documents({})
        available_books = db.books.count_documents({"available_copies": {"$gt": 0}})
        total_students = db.users.count_documents({"role": "student"})
        total_desks = db.desks.count_documents({})

        # Featured books (top 6 available books)
        featured_books = [Book(d) for d in db.books.find({"available_copies": {"$gt": 0}}).limit(6)]
        if not featured_books:
            featured_books = [Book(d) for d in db.books.find().limit(6)]

        # Categories list
        categories = list(db.categories.find().sort("name", 1).limit(6))

        stats = {
            'total_books': total_books,
            'available_books': available_books,
            'total_students': total_students,
            'total_desks': total_desks
        }

        return render_template(
            'index.html',
            stats=stats,
            featured_books=featured_books,
            categories=categories
        )

    # Error handlers
    @app.errorhandler(404)
    def page_not_found(e):
        return render_template('base.html', error_code=404, error_msg="The requested library page could not be found."), 404

    @app.errorhandler(500)
    def internal_error(e):
        return render_template('base.html', error_code=500, error_msg="An internal server error occurred."), 500

    # Auto seed initial data if empty
    with app.app_context():
        try:
            db = get_db(app.config)
            if db.books.count_documents({}) == 0:
                print("Database is empty. Automatically seeding initial records...")
                seed_database()
        except Exception as e:
            print(f"Notice during startup seed: {e}")

    return app

app = create_app()

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=True)
