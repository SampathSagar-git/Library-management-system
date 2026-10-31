from datetime import datetime, timezone
from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash
from bson import ObjectId
from models.neo4j_models import neo4j_service
from models.database import utc_now

class User(UserMixin):
    def __init__(self, data):
        self.data = data
        self.id = str(data.get('_id'))
        self.name = data.get('name', '')
        self.email = data.get('email', '')
        self.role = data.get('role', 'student') # 'student', 'staff', 'admin'
        self.department = data.get('department', 'General')
        self.student_id = data.get('student_id', '')
        self.staff_id = data.get('staff_id', '')
        self.phone = data.get('phone', '')
        self.status = data.get('status', 'active') # 'active', 'suspended'
        self.interests = data.get('interests', [])
        self.created_at = data.get('created_at', utc_now())

    @property
    def is_active(self):
        return self.status == 'active'

    @property
    def is_admin(self):
        return self.role == 'admin'

    @property
    def is_staff(self):
        return self.role == 'staff'

    @property
    def is_student(self):
        return self.role == 'student'

    def get_id(self):
        return self.id

    @staticmethod
    def get_by_id(db, user_id):
        if not user_id:
            return None
        try:
            doc = db.users.find_one({"_id": ObjectId(user_id) if ObjectId.is_valid(user_id) else user_id})
            if doc:
                return User(doc)
        except Exception:
            doc = db.users.find_one({"_id": user_id})
            if doc:
                return User(doc)
        return None

    @staticmethod
    def get_by_email(db, email):
        if not email:
            return None
        doc = db.users.find_one({"email": email.strip().lower()})
        return User(doc) if doc else None

    @staticmethod
    def create(db, name, email, password, role='student', department='General', 
               student_id='', staff_id='', phone='', interests=None):
        email_clean = email.strip().lower()
        if db.users.find_one({"email": email_clean}):
            return None, "An account with this email address already exists."

        pwd_hash = generate_password_hash(password)
        user_doc = {
            "name": name.strip(),
            "email": email_clean,
            "password_hash": pwd_hash,
            "role": role,
            "department": department.strip() if department else "General",
            "student_id": student_id.strip() if student_id else f"STU-{int(utc_now().timestamp()) % 100000}",
            "staff_id": staff_id.strip() if staff_id else (f"STF-{int(utc_now().timestamp()) % 100000}" if role == 'staff' else ""),
            "phone": phone.strip() if phone else "",
            "status": "active",
            "interests": interests or [],
            "created_at": utc_now()
        }

        result = db.users.insert_one(user_doc)
        new_id = str(result.inserted_id)
        user_doc['_id'] = result.inserted_id
        
        # Sync to Neo4j Graph
        try:
            neo4j_service.sync_user(new_id, user_doc['name'], user_doc['email'], role, user_doc['department'])
            for cat in (interests or []):
                neo4j_service.record_user_interest(new_id, cat, role)
        except Exception as e:
            pass

        return User(user_doc), None

    def check_password(self, password):
        return check_password_hash(self.data.get('password_hash', ''), password)

    @staticmethod
    def get_all(db, role=None, status=None, search=None):
        query = {}
        if role:
            query["role"] = role
        if status:
            query["status"] = status
        if search:
            query["$or"] = [
                {"name": {"$regex": search, "$options": "i"}},
                {"email": {"$regex": search, "$options": "i"}},
                {"department": {"$regex": search, "$options": "i"}},
                {"student_id": {"$regex": search, "$options": "i"}},
                {"staff_id": {"$regex": search, "$options": "i"}}
            ]
        docs = list(db.users.find(query).sort("created_at", -1))
        return [User(d) for d in docs]
