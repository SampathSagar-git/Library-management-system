import os
from dotenv import load_dotenv

load_dotenv()

class Config:
    SECRET_KEY = os.environ.get('SECRET_KEY', 'smart-library-secret-key-2026-v1-secure')
    
    # MongoDB Configuration
    MONGO_URI = os.environ.get('MONGO_URI', 'mongodb://localhost:27017/smart_library')
    MONGO_DBNAME = os.environ.get('MONGO_DBNAME', 'smart_library')
    
    # Neo4j Graph Database Configuration
    NEO4J_URI = os.environ.get('NEO4J_URI', 'bolt://localhost:7687')
    NEO4J_USER = os.environ.get('NEO4J_USER', 'neo4j')
    NEO4J_PASSWORD = os.environ.get('NEO4J_PASSWORD', 'library123')
    
    # Library Policy Settings
    STUDENT_LOAN_DAYS = 14
    STAFF_LOAN_DAYS = 30
    STUDENT_MAX_LOANS = 5
    STAFF_MAX_LOANS = 10
    FINE_PER_DAY = 1.0  # $1.00 per day overdue
    MAX_DESK_HOURS_PER_DAY = 6
    
    # Mail settings (mock or SMTP)
    MAIL_SERVER = os.environ.get('MAIL_SERVER', 'smtp.gmail.com')
    MAIL_PORT = int(os.environ.get('MAIL_PORT', 587))
    MAIL_USE_TLS = os.environ.get('MAIL_USE_TLS', 'true').lower() in ['true', '1']
    MAIL_USERNAME = os.environ.get('MAIL_USERNAME', '')
    MAIL_PASSWORD = os.environ.get('MAIL_PASSWORD', '')
    MAIL_DEFAULT_SENDER = os.environ.get('MAIL_DEFAULT_SENDER', 'noreply@smartlibrary.edu')
