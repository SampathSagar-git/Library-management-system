import os
from datetime import datetime, timedelta
from werkzeug.security import generate_password_hash
from models.database import get_db
from models.neo4j_models import neo4j_service
from config import Config

def seed_database():
    print("[*] Initializing Smart Library Database Seeding...")
    db = get_db(Config)

    # 1. Categories
    categories = [
        {"name": "Computer Science & AI", "description": "Artificial Intelligence, Deep Learning, and Neural Systems", "color_code": "#2563eb", "icon": "fa-brain"},
        {"name": "Data Science & Analytics", "description": "Big Data, Statistical Inference, and Machine Learning", "color_code": "#0284c7", "icon": "fa-chart-pie"},
        {"name": "Software Engineering", "description": "System Design, Clean Architecture, and DevOps", "color_code": "#7c3aed", "icon": "fa-code"},
        {"name": "Mathematics & Algorithms", "description": "Discrete Math, Optimization, and Algorithm Design", "color_code": "#059669", "icon": "fa-square-root-variable"},
        {"name": "Physics & Quantum", "description": "Quantum Computing, Mechanics, and Modern Physics", "color_code": "#d97706", "icon": "fa-atom"},
        {"name": "Literature & Philosophy", "description": "Classic and Modern World Literature and Ethics", "color_code": "#db2777", "icon": "fa-feather-pointed"},
        {"name": "Business & Leadership", "description": "Technology Management, Entrepreneurship, and Strategy", "color_code": "#4f46e5", "icon": "fa-briefcase"}
    ]

    for cat in categories:
        db.categories.update_one({"name": cat["name"]}, {"$set": cat}, upsert=True)
    print(f"[OK] Seeded {len(categories)} categories")

    # 2. Desks (Library Floor Layout)
    desks_data = [
        # Zone A - Quiet Pods (Individual)
        {"desk_number": "A101", "zone": "Quiet Study Pods", "has_power": True, "has_monitor": False, "status": "available"},
        {"desk_number": "A102", "zone": "Quiet Study Pods", "has_power": True, "has_monitor": False, "status": "available"},
        {"desk_number": "A103", "zone": "Quiet Study Pods", "has_power": True, "has_monitor": False, "status": "available"},
        {"desk_number": "A104", "zone": "Quiet Study Pods", "has_power": True, "has_monitor": False, "status": "available"},
        # Zone B - Collaborative Study Tables
        {"desk_number": "B201", "zone": "Collaborative Zone", "has_power": True, "has_monitor": False, "status": "available"},
        {"desk_number": "B202", "zone": "Collaborative Zone", "has_power": True, "has_monitor": False, "status": "available"},
        {"desk_number": "B203", "zone": "Collaborative Zone", "has_power": True, "has_monitor": False, "status": "available"},
        {"desk_number": "B204", "zone": "Collaborative Zone", "has_power": True, "has_monitor": False, "status": "available"},
        # Zone C - Tech & Media Lab
        {"desk_number": "C301", "zone": "Tech & Media Lab", "has_power": True, "has_monitor": True, "status": "available"},
        {"desk_number": "C302", "zone": "Tech & Media Lab", "has_power": True, "has_monitor": True, "status": "available"},
        {"desk_number": "C303", "zone": "Tech & Media Lab", "has_power": True, "has_monitor": True, "status": "available"},
        {"desk_number": "C304", "zone": "Tech & Media Lab", "has_power": True, "has_monitor": True, "status": "available"},
        # Zone D - Faculty & Research Suites
        {"desk_number": "D401", "zone": "Faculty & Research Suites", "has_power": True, "has_monitor": True, "status": "available"},
        {"desk_number": "D402", "zone": "Faculty & Research Suites", "has_power": True, "has_monitor": True, "status": "available"},
        {"desk_number": "D403", "zone": "Faculty & Research Suites", "has_power": True, "has_monitor": True, "status": "available"},
        {"desk_number": "D404", "zone": "Faculty & Research Suites", "has_power": True, "has_monitor": True, "status": "available"},
    ]

    for d in desks_data:
        db.desks.update_one({"desk_number": d["desk_number"]}, {"$set": d}, upsert=True)
        neo4j_service.sync_desk(d["desk_number"], d["zone"])
    print(f"[OK] Seeded {len(desks_data)} visual library desks")

    # 3. Users (Admin, Staff, Students)
    users_data = [
        {
            "name": "Dr. Eleanor Vance",
            "email": "admin@library.edu",
            "password_hash": generate_password_hash("Admin@123"),
            "role": "admin",
            "department": "Library Administration",
            "staff_id": "ADM-001",
            "student_id": "",
            "phone": "+1 (555) 019-2831",
            "status": "active",
            "interests": ["Computer Science & AI", "Business & Leadership"],
            "created_at": datetime.utcnow()
        },
        {
            "name": "Prof. David Miller",
            "email": "prof.smith@library.edu",
            "password_hash": generate_password_hash("Staff@123"),
            "role": "staff",
            "department": "Computer Science & Engineering",
            "staff_id": "FAC-102",
            "student_id": "",
            "phone": "+1 (555) 014-9921",
            "status": "active",
            "interests": ["Computer Science & AI", "Mathematics & Algorithms"],
            "created_at": datetime.utcnow()
        },
        {
            "name": "Alex Turner",
            "email": "alex@student.edu",
            "password_hash": generate_password_hash("Student@123"),
            "role": "student",
            "department": "Data Science & AI",
            "staff_id": "",
            "student_id": "STU-2024-8841",
            "phone": "+1 (555) 018-7722",
            "status": "active",
            "interests": ["Computer Science & AI", "Data Science & Analytics"],
            "created_at": datetime.utcnow()
        },
        {
            "name": "Sarah Jenkins",
            "email": "sarah@student.edu",
            "password_hash": generate_password_hash("Student@123"),
            "role": "student",
            "department": "Software Systems",
            "staff_id": "",
            "student_id": "STU-2024-9102",
            "phone": "+1 (555) 012-3489",
            "status": "active",
            "interests": ["Software Engineering", "Mathematics & Algorithms"],
            "created_at": datetime.utcnow()
        },
        {
            "name": "Michael Chen",
            "email": "michael@student.edu",
            "password_hash": generate_password_hash("Student@123"),
            "role": "student",
            "department": "Applied Physics",
            "staff_id": "",
            "student_id": "STU-2024-7341",
            "phone": "+1 (555) 017-5501",
            "status": "active",
            "interests": ["Physics & Quantum", "Mathematics & Algorithms"],
            "created_at": datetime.utcnow()
        }
    ]

    user_map = {}
    for u in users_data:
        curr = db.users.find_one({"email": u["email"]})
        if not curr:
            res = db.users.insert_one(u)
            uid = str(res.inserted_id)
        else:
            uid = str(curr["_id"])
        user_map[u["email"]] = uid
        neo4j_service.sync_user(uid, u["name"], u["email"], u["role"], u["department"])
        for cat in u["interests"]:
            neo4j_service.record_user_interest(uid, cat, u["role"])
    print(f"[OK] Seeded {len(users_data)} users with Neo4j interest nodes")

    # 4. Books
    books_data = [
        {
            "title": "Artificial Intelligence: A Modern Approach",
            "author": "Stuart Russell & Peter Norvig",
            "isbn": "978-0134610993",
            "category": "Computer Science & AI",
            "publisher": "Pearson",
            "quantity": 5,
            "available_copies": 3,
            "cover_image": "https://images.unsplash.com/photo-1620712943543-bcc4688e7485?auto=format&fit=crop&w=600&q=80",
            "description": "The definitive comprehensive introduction to artificial intelligence, search algorithms, knowledge graphs, and neural systems.",
            "location": "Floor 2 - Shelf CS-101",
            "tags": ["AI", "Machine Learning", "Algorithms"],
            "publication_year": 2021
        },
        {
            "title": "Designing Data-Intensive Applications",
            "author": "Martin Fowler",
            "isbn": "978-1449373320",
            "category": "Software Engineering",
            "publisher": "O'Reilly Media",
            "quantity": 4,
            "available_copies": 2,
            "cover_image": "https://images.unsplash.com/photo-1517694712202-14dd9538aa97?auto=format&fit=crop&w=600&q=80",
            "description": "The big ideas behind reliable, scalable, and maintainable systems, distributed transactions, and event streaming.",
            "location": "Floor 2 - Shelf SE-204",
            "tags": ["Architecture", "Distributed Systems", "Cloud"],
            "publication_year": 2020
        },
        {
            "title": "Introduction to Algorithms (CLRS)",
            "author": "Thomas Cormen & Ronald Rivest",
            "isbn": "978-0262046305",
            "category": "Mathematics & Algorithms",
            "publisher": "MIT Press",
            "quantity": 6,
            "available_copies": 4,
            "cover_image": "https://images.unsplash.com/photo-1509228468518-180dd4864904?auto=format&fit=crop&w=600&q=80",
            "description": "In-depth reference manual on graph theory, dynamic programming, algorithmic complexity, and numerical algorithms.",
            "location": "Floor 1 - Shelf MA-301",
            "tags": ["Algorithms", "Data Structures", "MIT"],
            "publication_year": 2022
        },
        {
            "title": "Deep Learning with Python",
            "author": "François Chollet",
            "isbn": "978-1617296864",
            "category": "Data Science & Analytics",
            "publisher": "Manning Publications",
            "quantity": 4,
            "available_copies": 1,
            "cover_image": "https://images.unsplash.com/photo-1555949963-ff9fe0c870eb?auto=format&fit=crop&w=600&q=80",
            "description": "Hands-on guide to computer vision, natural language processing, and generative AI models using Keras and TensorFlow.",
            "location": "Floor 2 - Shelf DS-115",
            "tags": ["Deep Learning", "Python", "Neural Networks"],
            "publication_year": 2021
        },
        {
            "title": "Clean Code: A Handbook of Agile Software Craftsmanship",
            "author": "Robert C. Martin",
            "isbn": "978-0132350884",
            "category": "Software Engineering",
            "publisher": "Prentice Hall",
            "quantity": 5,
            "available_copies": 4,
            "cover_image": "https://images.unsplash.com/photo-1532012164546-f432f2e3777a?auto=format&fit=crop&w=600&q=80",
            "description": "A must-read handbook for software engineers on writing clean, readable, testable, and refactorable code.",
            "location": "Floor 2 - Shelf SE-102",
            "tags": ["Clean Code", "Best Practices", "Refactoring"],
            "publication_year": 2019
        },
        {
            "title": "Quantum Computing: An Applied Approach",
            "author": "Jack D. Hidary",
            "isbn": "978-3030832735",
            "category": "Physics & Quantum",
            "publisher": "Springer",
            "quantity": 3,
            "available_copies": 2,
            "cover_image": "https://images.unsplash.com/photo-1635070041078-e363dbe005cb?auto=format&fit=crop&w=600&q=80",
            "description": "Comprehensive textbook covering quantum circuits, superposition, Shor's algorithm, and quantum machine learning.",
            "location": "Floor 3 - Shelf PH-402",
            "tags": ["Quantum", "Physics", "Qubits"],
            "publication_year": 2023
        },
        {
            "title": "The Pragmatic Programmer",
            "author": "Andrew Hunt & David Thomas",
            "isbn": "978-0135957059",
            "category": "Software Engineering",
            "publisher": "Addison-Wesley",
            "quantity": 4,
            "available_copies": 3,
            "cover_image": "https://images.unsplash.com/photo-1512820790803-83ca734da794?auto=format&fit=crop&w=600&q=80",
            "description": "From journey of a coder to a master software engineer, cutting through technical debt and modern paradigms.",
            "location": "Floor 2 - Shelf SE-108",
            "tags": ["Programming", "Career", "Craftsmanship"],
            "publication_year": 2020
        },
        {
            "title": "Hands-On Machine Learning with Scikit-Learn",
            "author": "Aurélien Géron",
            "isbn": "978-1098125974",
            "category": "Data Science & Analytics",
            "publisher": "O'Reilly Media",
            "quantity": 5,
            "available_copies": 2,
            "cover_image": "https://images.unsplash.com/photo-1526374965328-7f61d4dc18c5?auto=format&fit=crop&w=600&q=80",
            "description": "A practical concrete guide to end-to-end machine learning workflows, model tuning, and neural networks.",
            "location": "Floor 2 - Shelf DS-118",
            "tags": ["Machine Learning", "Scikit-Learn", "Python"],
            "publication_year": 2023
        }
    ]

    book_map = {}
    for b in books_data:
        curr = db.books.find_one({"isbn": b["isbn"]})
        if not curr:
            b["created_at"] = datetime.utcnow()
            res = db.books.insert_one(b)
            bid = str(res.inserted_id)
        else:
            bid = str(curr["_id"])
        book_map[b["isbn"]] = bid
        neo4j_service.sync_book(bid, b["title"], b["author"], b["isbn"], b["category"])
    print(f"[OK] Seeded {len(books_data)} books and synced with Neo4j")

    # 5. Create Pre-existing Loans & Reservations for realistic Graph recommendations
    alex_id = user_map.get("alex@student.edu")
    sarah_id = user_map.get("sarah@student.edu")
    prof_id = user_map.get("prof.smith@library.edu")
    ai_book_id = book_map.get("978-0134610993")
    clrs_book_id = book_map.get("978-0262046305")
    deep_learning_id = book_map.get("978-1617296864")
    ddia_id = book_map.get("978-1449373320")

    now = datetime.utcnow()

    # Loan 1: Alex borrowed AI book
    if db.loans.count_documents({"user_id": alex_id}) == 0:
        loan1 = {
            "book_id": ai_book_id,
            "book_title": "Artificial Intelligence: A Modern Approach",
            "book_author": "Stuart Russell & Peter Norvig",
            "book_cover": "https://images.unsplash.com/photo-1620712943543-bcc4688e7485?auto=format&fit=crop&w=600&q=80",
            "book_isbn": "978-0134610993",
            "user_id": alex_id,
            "user_name": "Alex Turner",
            "user_email": "alex@student.edu",
            "user_role": "student",
            "issue_date": now - timedelta(days=5),
            "due_date": now + timedelta(days=9),
            "return_date": None,
            "status": "active",
            "renew_count": 0,
            "fine_amount": 0.0,
            "fine_status": "none",
            "created_at": now - timedelta(days=5)
        }
        res1 = db.loans.insert_one(loan1)
        neo4j_service.record_borrow(alex_id, ai_book_id, "student", loan_id=str(res1.inserted_id))

    # Loan 2: Sarah borrowed AI book and DDIA
    if db.loans.count_documents({"user_id": sarah_id}) == 0:
        loan2 = {
            "book_id": ai_book_id,
            "book_title": "Artificial Intelligence: A Modern Approach",
            "book_author": "Stuart Russell & Peter Norvig",
            "book_cover": "https://images.unsplash.com/photo-1620712943543-bcc4688e7485?auto=format&fit=crop&w=600&q=80",
            "book_isbn": "978-0134610993",
            "user_id": sarah_id,
            "user_name": "Sarah Jenkins",
            "user_email": "sarah@student.edu",
            "user_role": "student",
            "issue_date": now - timedelta(days=10),
            "due_date": now + timedelta(days=4),
            "return_date": None,
            "status": "active",
            "renew_count": 0,
            "fine_amount": 0.0,
            "fine_status": "none",
            "created_at": now - timedelta(days=10)
        }
        res2 = db.loans.insert_one(loan2)
        neo4j_service.record_borrow(sarah_id, ai_book_id, "student", loan_id=str(res2.inserted_id))

        loan3 = {
            "book_id": ddia_id,
            "book_title": "Designing Data-Intensive Applications",
            "book_author": "Martin Fowler",
            "book_cover": "https://images.unsplash.com/photo-1517694712202-14dd9538aa97?auto=format&fit=crop&w=600&q=80",
            "book_isbn": "978-1449373320",
            "user_id": sarah_id,
            "user_name": "Sarah Jenkins",
            "user_email": "sarah@student.edu",
            "user_role": "student",
            "issue_date": now - timedelta(days=20),
            "due_date": now - timedelta(days=6),
            "return_date": now - timedelta(days=5),
            "status": "returned",
            "renew_count": 0,
            "fine_amount": 1.0,
            "fine_status": "paid",
            "created_at": now - timedelta(days=20)
        }
        res3 = db.loans.insert_one(loan3)
        neo4j_service.record_borrow(sarah_id, ddia_id, "student", loan_id=str(res3.inserted_id))

    # Desk Bookings for today
    today_str = now.strftime('%Y-%m-%d')
    if db.desk_reservations.count_documents({"booking_date": today_str}) == 0:
        db.desk_reservations.insert_one({
            "desk_number": "A101",
            "zone": "Quiet Study Pods",
            "user_id": alex_id,
            "user_name": "Alex Turner",
            "user_email": "alex@student.edu",
            "user_role": "student",
            "booking_date": today_str,
            "start_time": "14:00",
            "end_time": "16:00",
            "duration_hours": 2,
            "purpose": "Study for Machine Learning Finals",
            "status": "confirmed",
            "created_at": now - timedelta(hours=3)
        })
        neo4j_service.record_desk_booking(alex_id, "A101", "student", today_str, "14:00")

        db.desk_reservations.insert_one({
            "desk_number": "D401",
            "zone": "Faculty & Research Suites",
            "user_id": prof_id,
            "user_name": "Prof. David Miller",
            "user_email": "prof.smith@library.edu",
            "user_role": "staff",
            "booking_date": today_str,
            "start_time": "10:00",
            "end_time": "13:00",
            "duration_hours": 3,
            "purpose": "Faculty Research & Thesis Review",
            "status": "confirmed",
            "created_at": now - timedelta(hours=5)
        })
        neo4j_service.record_desk_booking(prof_id, "D401", "staff", today_str, "10:00")

    # Initial Activity Logs
    if db.activity_logs.count_documents({}) == 0:
        db.activity_logs.insert_one({
            "user_id": user_map.get("admin@library.edu"),
            "user_name": "Dr. Eleanor Vance",
            "action": "SYSTEM_INIT",
            "details": "Smart Library Management System initialized with sample academic resources.",
            "ip_address": "127.0.0.1",
            "timestamp": now - timedelta(days=1)
        })

    print("[SUCCESS] Database seeding completed successfully!")

if __name__ == '__main__':
    seed_database()
