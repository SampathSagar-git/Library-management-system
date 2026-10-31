import logging
import os
import json
from datetime import datetime, timezone
from pymongo import MongoClient
import pymongo.errors
from bson import ObjectId

def utc_now():
    return datetime.now(timezone.utc).replace(tzinfo=None)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Global mongo client and db reference
_client = None
_db = None
_is_mock = False

def get_db(config=None):
    global _client, _db, _is_mock
    if _db is not None:
        return _db

    if config is not None:
        if hasattr(config, 'get'):
            uri = config.get('MONGO_URI', 'mongodb://localhost:27017/smart_library')
            dbname = config.get('MONGO_DBNAME', 'smart_library')
        else:
            uri = getattr(config, 'MONGO_URI', 'mongodb://localhost:27017/smart_library')
            dbname = getattr(config, 'MONGO_DBNAME', 'smart_library')
    else:
        uri = os.environ.get('MONGO_URI', 'mongodb://localhost:27017/smart_library')
        dbname = os.environ.get('MONGO_DBNAME', 'smart_library')
    
    try:
        # Attempt connection to real MongoDB with short timeout
        real_client = MongoClient(uri, serverSelectionTimeoutMS=1500)
        # Trigger server check
        real_client.server_info()
        _client = real_client
        _db = _client[dbname]
        _is_mock = False
        logger.info(f"Connected successfully to real MongoDB at {uri}")
        init_indexes(_db)
    except Exception as e:
        logger.warning(f"Could not connect to MongoDB ({e}). Falling back to in-memory PyMongo mock client for instant zero-config operation.")
        import mongomock
        _client = mongomock.MongoClient()
        _db = _client[dbname]
        _is_mock = True
        
    return _db

def is_mongo_mock():
    global _is_mock
    return _is_mock

def init_indexes(db):
    try:
        # User unique email index
        db.users.create_index("email", unique=True)
        # Books ISBN index
        db.books.create_index("isbn", unique=True)
        # Book reservation indexes
        db.book_reservations.create_index([("user_id", 1), ("book_id", 1)])
        # Desk reservation collision index
        db.desk_reservations.create_index([("desk_number", 1), ("booking_date", 1), ("start_time", 1)])
        # Loans index
        db.loans.create_index([("user_id", 1), ("status", 1)])
    except Exception as e:
        logger.warning(f"Index creation notice: {e}")

def log_activity(db, user_id, user_name, action, details, ip_address="127.0.0.1"):
    try:
        db.activity_logs.insert_one({
            "user_id": str(user_id) if user_id else "guest",
            "user_name": user_name or "Guest",
            "action": action,
            "details": details,
            "ip_address": ip_address,
            "timestamp": utc_now()
        })
    except Exception as e:
        logger.error(f"Failed to log activity: {e}")

def create_notification(db, user_id, title, message, notif_type="info"):
    try:
        db.notifications.insert_one({
            "user_id": str(user_id),
            "title": title,
            "message": message,
            "type": notif_type,
            "is_read": False,
            "created_at": utc_now()
        })
    except Exception as e:
        logger.error(f"Failed to create notification: {e}")
