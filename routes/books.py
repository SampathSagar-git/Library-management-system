from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify, current_app
from flask_login import login_required, current_user
from models.book import Book
from models.database import get_db, log_activity
from models.neo4j_models import neo4j_service

books_bp = Blueprint('books', __name__)

@books_bp.route('/books')
def catalog():
    db = get_db(current_app.config)
    query = request.args.get('q', '').strip()
    category = request.args.get('category', 'all')
    author = request.args.get('author', 'all')
    availability = request.args.get('availability', 'all')
    sort_by = request.args.get('sort', 'newest')
    page = max(1, int(request.args.get('page', 1)))
    per_page = 12
    skip = (page - 1) * per_page

    books, total_count = Book.search_and_filter(
        db, query=query, category=category, author=author,
        availability=availability, sort_by=sort_by, skip=skip, limit=per_page
    )

    categories = list(db.categories.find().sort("name", 1))
    authors = db.books.distinct("author")
    total_pages = max(1, (total_count + per_page - 1) // per_page)

    return render_template(
        'books.html',
        books=books,
        total_count=total_count,
        categories=categories,
        authors=sorted(authors),
        selected_category=category,
        selected_author=author,
        selected_avail=availability,
        selected_sort=sort_by,
        search_query=query,
        page=page,
        total_pages=total_pages
    )

@books_bp.route('/books/add', methods=['POST'])
@login_required
def add_book():
    if not current_user.is_admin:
        flash('Unauthorized access: Administrator privilege required.', 'danger')
        return redirect(url_for('books.catalog'))

    db = get_db(current_app.config)
    title = request.form.get('title', '').strip()
    author = request.form.get('author', '').strip()
    isbn = request.form.get('isbn', '').strip()
    category = request.form.get('category', 'General').strip()
    publisher = request.form.get('publisher', '').strip()
    quantity = int(request.form.get('quantity', 1))
    cover_image = request.form.get('cover_image', '').strip()
    description = request.form.get('description', '').strip()
    location = request.form.get('location', '').strip()
    year = int(request.form.get('publication_year', 2024))

    if not title or not author or not isbn:
        flash('Title, Author, and ISBN are required.', 'warning')
        return redirect(request.referrer or url_for('admin.dashboard'))

    book, err = Book.create(
        db, title=title, author=author, isbn=isbn, category=category,
        quantity=quantity, publisher=publisher, cover_image=cover_image,
        description=description, location=location, publication_year=year
    )

    if err:
        flash(err, 'danger')
    else:
        log_activity(db, current_user.id, current_user.name, "ADD_BOOK", f"Added new book '{title}' (ISBN: {isbn})")
        flash(f"Book '{title}' successfully added to catalog.", 'success')

    return redirect(request.referrer or url_for('admin.dashboard'))

@books_bp.route('/books/edit/<book_id>', methods=['POST'])
@login_required
def edit_book(book_id):
    if not current_user.is_admin:
        flash('Unauthorized access: Administrator privilege required.', 'danger')
        return redirect(url_for('books.catalog'))

    db = get_db(current_app.config)
    update_data = {
        "title": request.form.get('title', '').strip(),
        "author": request.form.get('author', '').strip(),
        "category": request.form.get('category', '').strip(),
        "publisher": request.form.get('publisher', '').strip(),
        "quantity": int(request.form.get('quantity', 1)),
        "cover_image": request.form.get('cover_image', '').strip(),
        "description": request.form.get('description', '').strip(),
        "location": request.form.get('location', '').strip(),
        "publication_year": int(request.form.get('publication_year', 2024))
    }

    success, err = Book.update(db, book_id, update_data)
    if success:
        log_activity(db, current_user.id, current_user.name, "EDIT_BOOK", f"Updated book {book_id}")
        flash('Book details updated successfully.', 'success')
    else:
        flash(f'Failed to update book: {err}', 'danger')

    return redirect(request.referrer or url_for('admin.dashboard'))

@books_bp.route('/books/delete/<book_id>', methods=['POST'])
@login_required
def delete_book(book_id):
    if not current_user.is_admin:
        flash('Unauthorized access: Administrator privilege required.', 'danger')
        return redirect(url_for('books.catalog'))

    db = get_db(current_app.config)
    success, err = Book.delete(db, book_id)
    if success:
        log_activity(db, current_user.id, current_user.name, "DELETE_BOOK", f"Deleted book {book_id}")
        flash('Book successfully removed from catalog.', 'success')
    else:
        flash(f'Cannot delete book: {err}', 'danger')

    return redirect(request.referrer or url_for('admin.dashboard'))

@books_bp.route('/api/books/<book_id>')
def get_book_json(book_id):
    db = get_db(current_app.config)
    book = Book.get_by_id(db, book_id)
    if not book:
        return jsonify({"error": "Book not found"}), 404
        
    data = dict(book.data)
    data['_id'] = str(data.get('_id'))
    data['available_copies'] = book.available_copies
    data['borrowed_copies'] = book.borrowed_copies
    data['is_available'] = book.is_available
    return jsonify(data)
