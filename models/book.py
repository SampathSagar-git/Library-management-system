from datetime import datetime, timezone
from bson import ObjectId
from models.neo4j_models import neo4j_service
from models.database import utc_now

class Book:
    def __init__(self, data):
        self.data = data
        self.id = str(data.get('_id'))
        self.title = data.get('title', '')
        self.author = data.get('author', '')
        self.isbn = data.get('isbn', '')
        self.publisher = data.get('publisher', '')
        self.category = data.get('category', 'General')
        self.quantity = int(data.get('quantity', 1))
        self.available_copies = int(data.get('available_copies', self.quantity))
        self.borrowed_copies = self.quantity - self.available_copies
        self.cover_image = data.get('cover_image', '') or 'https://images.unsplash.com/photo-1544947950-fa07a98d237f?auto=format&fit=crop&w=600&q=80'
        self.description = data.get('description', '')
        self.location = data.get('location', 'Main Hall - Section A')
        self.tags = data.get('tags', [])
        self.publication_year = data.get('publication_year', 2024)
        self.created_at = data.get('created_at', utc_now())

    @property
    def is_available(self):
        return self.available_copies > 0

    @staticmethod
    def get_by_id(db, book_id):
        if not book_id:
            return None
        try:
            doc = db.books.find_one({"_id": ObjectId(book_id) if ObjectId.is_valid(book_id) else book_id})
        except Exception:
            doc = db.books.find_one({"_id": book_id})
        return Book(doc) if doc else None

    @staticmethod
    def get_by_isbn(db, isbn):
        if not isbn:
            return None
        doc = db.books.find_one({"isbn": isbn.strip()})
        return Book(doc) if doc else None

    @staticmethod
    def create(db, title, author, isbn, category, quantity=1, publisher="", 
               cover_image="", description="", location="", tags=None, publication_year=2024):
        isbn_clean = isbn.strip()
        if db.books.find_one({"isbn": isbn_clean}):
            return None, "A book with this ISBN already exists."

        qty = max(1, int(quantity))
        book_doc = {
            "title": title.strip(),
            "author": author.strip(),
            "isbn": isbn_clean,
            "category": category.strip() if category else "General",
            "quantity": qty,
            "available_copies": qty,
            "publisher": publisher.strip() if publisher else "Academic Press",
            "cover_image": cover_image.strip() if cover_image else "https://images.unsplash.com/photo-1544947950-fa07a98d237f?auto=format&fit=crop&w=600&q=80",
            "description": description.strip() if description else "Essential academic reading and reference book.",
            "location": location.strip() if location else "Floor 1 - Section A",
            "tags": tags or [category],
            "publication_year": int(publication_year) if publication_year else 2024,
            "created_at": utc_now()
        }

        result = db.books.insert_one(book_doc)
        new_id = str(result.inserted_id)
        book_doc['_id'] = result.inserted_id

        # Update category count
        db.categories.update_one(
            {"name": book_doc['category']},
            {"$inc": {"book_count": 1}, "$setOnInsert": {"description": f"Books in {book_doc['category']}"}},
            upsert=True
        )

        # Sync with Neo4j Graph
        try:
            neo4j_service.sync_book(new_id, book_doc['title'], book_doc['author'], book_doc['isbn'], book_doc['category'])
        except Exception:
            pass

        return Book(book_doc), None

    @staticmethod
    def update(db, book_id, update_data):
        try:
            oid = ObjectId(book_id) if ObjectId.is_valid(book_id) else book_id
            curr = db.books.find_one({"_id": oid})
            if not curr:
                return False, "Book not found."

            if 'quantity' in update_data:
                new_qty = int(update_data['quantity'])
                borrowed = curr.get('quantity', 1) - curr.get('available_copies', 1)
                if new_qty < borrowed:
                    return False, f"Cannot reduce total quantity below currently borrowed count ({borrowed})."
                update_data['available_copies'] = new_qty - borrowed

            update_data['updated_at'] = utc_now()
            db.books.update_one({"_id": oid}, {"$set": update_data})
            
            # Sync to Neo4j
            updated_doc = db.books.find_one({"_id": oid})
            if updated_doc:
                neo4j_service.sync_book(
                    str(oid), 
                    updated_doc.get('title'), 
                    updated_doc.get('author'), 
                    updated_doc.get('isbn'), 
                    updated_doc.get('category')
                )
            return True, None
        except Exception as e:
            return False, str(e)

    @staticmethod
    def delete(db, book_id):
        try:
            oid = ObjectId(book_id) if ObjectId.is_valid(book_id) else book_id
            # Check if active loans exist
            active_loan = db.loans.find_one({"book_id": str(oid), "status": "active"})
            if active_loan:
                return False, "Cannot delete book while copies are currently out on active loan."

            db.books.delete_one({"_id": oid})
            return True, None
        except Exception as e:
            return False, str(e)

    @staticmethod
    def search_and_filter(db, query=None, category=None, author=None, availability=None, sort_by='newest', skip=0, limit=24):
        filter_dict = {}
        
        if query:
            filter_dict["$or"] = [
                {"title": {"$regex": query, "$options": "i"}},
                {"author": {"$regex": query, "$options": "i"}},
                {"isbn": {"$regex": query, "$options": "i"}},
                {"category": {"$regex": query, "$options": "i"}},
                {"description": {"$regex": query, "$options": "i"}}
            ]
        if category and category != 'all':
            filter_dict["category"] = category
        if author and author != 'all':
            filter_dict["author"] = author
        if availability == 'available':
            filter_dict["available_copies"] = {"$gt": 0}
        elif availability == 'reserved':
            filter_dict["available_copies"] = 0

        sort_map = {
            'newest': ("created_at", -1),
            'title_asc': ("title", 1),
            'title_desc': ("title", -1),
            'popular': ("quantity", -1),
            'available': ("available_copies", -1)
        }
        sort_field, sort_dir = sort_map.get(sort_by, ("created_at", -1))

        total_count = db.books.count_documents(filter_dict)
        cursor = db.books.find(filter_dict).sort(sort_field, sort_dir).skip(skip).limit(limit)
        books = [Book(d) for d in cursor]
        return books, total_count
