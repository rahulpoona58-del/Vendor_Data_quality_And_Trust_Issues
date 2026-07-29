import os
from pathlib import Path
from dotenv import load_dotenv

# Base directory of the project
BASE_DIR = Path(__file__).resolve().parent.parent

# Load environment variables from .env if it exists
dotenv_path = BASE_DIR / '.env'
if dotenv_path.exists():
    load_dotenv(dotenv_path)

class Config:
    """Base Configuration Class containing common environment settings."""
    SECRET_KEY = os.getenv('SECRET_KEY', 'dev-secret-key-change-in-production')
    JWT_SECRET_KEY = os.getenv('JWT_SECRET_KEY', 'jwt-secret-key-change-in-production')
    
    # Storage & Files
    CSV_DATA_PATH = os.getenv('CSV_DATA_PATH', str(BASE_DIR / 'vendors_20_columns.csv'))
    UPLOAD_FOLDER = os.getenv('UPLOAD_FOLDER', str(BASE_DIR / 'uploads'))
    MAX_CONTENT_LENGTH = int(os.getenv('MAX_CONTENT_LENGTH', 16 * 1024 * 1024))  # 16 MB limit
    
    # Logging Configuration
    LOG_LEVEL = os.getenv('LOG_LEVEL', 'INFO').upper()
    LOG_FILE_PATH = os.getenv('LOG_FILE_PATH', str(BASE_DIR / 'logs' / 'app.log'))
    
    # AI/ML Configuration
    AI_MODEL_PATH = os.getenv('AI_MODEL_PATH', str(BASE_DIR / 'src' / 'infrastructure' / 'ml' / 'models'))
    AI_CONFIDENCE_THRESHOLD = float(os.getenv('AI_CONFIDENCE_THRESHOLD', 0.75))
    
    # Database Configuration
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    SQLALCHEMY_DATABASE_URI = os.getenv('DATABASE_URL', f"sqlite:///{BASE_DIR / 'instance' / 'vendor_trust.db'}")
    
    # Cache & Messaging Configuration
    REDIS_URL = os.getenv('REDIS_URL', 'redis://localhost:6379/0')
    
    # Security Configuration Default
    SECURITY_HEADERS_ENABLED = True
    CSRF_ENABLED = os.getenv('CSRF_ENABLED', 'True').lower() in ('true', '1', 't')
    
    # Rate Limiting Configuration (Requests per Window in Seconds)
    RATE_LIMIT_LOGIN_COUNT = int(os.getenv('RATE_LIMIT_LOGIN_COUNT', 5))
    RATE_LIMIT_LOGIN_WINDOW = int(os.getenv('RATE_LIMIT_LOGIN_WINDOW', 60))
    
    RATE_LIMIT_SEARCH_COUNT = int(os.getenv('RATE_LIMIT_SEARCH_COUNT', 30))
    RATE_LIMIT_SEARCH_WINDOW = int(os.getenv('RATE_LIMIT_SEARCH_WINDOW', 60))
    
    RATE_LIMIT_AI_COUNT = int(os.getenv('RATE_LIMIT_AI_COUNT', 15))
    RATE_LIMIT_AI_WINDOW = int(os.getenv('RATE_LIMIT_AI_WINDOW', 60))
    
    RATE_LIMIT_UPLOAD_COUNT = int(os.getenv('RATE_LIMIT_UPLOAD_COUNT', 10))
    RATE_LIMIT_UPLOAD_WINDOW = int(os.getenv('RATE_LIMIT_UPLOAD_WINDOW', 60))

class DevelopmentConfig(Config):
    """Development Environment Settings."""
    DEBUG = True
    TESTING = False
    LOG_LEVEL = os.getenv('LOG_LEVEL', 'DEBUG').upper()
    SQLALCHEMY_DATABASE_URI = os.getenv('DATABASE_URL', f"sqlite:///{BASE_DIR / 'instance' / 'vendor_trust.db'}")

class TestingConfig(Config):
    """Testing Environment Settings."""
    TESTING = True
    DEBUG = True
    SQLALCHEMY_DATABASE_URI = os.getenv('TEST_DATABASE_URL', 'sqlite:///:memory:')
    CSV_DATA_PATH = os.getenv('CSV_DATA_PATH_TEST', str(BASE_DIR / 'vendors_20_columns.csv'))
    SECURITY_HEADERS_ENABLED = False
    CSRF_ENABLED = False

class ProductionConfig(Config):
    """Production Environment Settings."""
    DEBUG = False
    TESTING = False
    LOG_LEVEL = os.getenv('LOG_LEVEL', 'WARNING').upper()
    SQLALCHEMY_DATABASE_URI = os.getenv('DATABASE_URL')
    
    def __init__(self):
        super().__init__()
        # Validate that essential secrets are configured in production
        if not os.getenv('SECRET_KEY') or self.SECRET_KEY == 'dev-secret-key-change-in-production':
            raise ValueError("CRITICAL: SECRET_KEY environment variable MUST be set in production!")
        if not os.getenv('JWT_SECRET_KEY') or self.JWT_SECRET_KEY == 'jwt-secret-key-change-in-production':
            raise ValueError("CRITICAL: JWT_SECRET_KEY environment variable MUST be set in production!")
        if not self.SQLALCHEMY_DATABASE_URI:
            raise ValueError("CRITICAL: DATABASE_URL environment variable MUST be set in production!")

# Mapping of configurations to string identifiers
config_by_name = {
    'development': DevelopmentConfig,
    'testing': TestingConfig,
    'production': ProductionConfig,
    'default': DevelopmentConfig
}

def get_config():
    """Resolves and returns the active configuration class instance based on FLASK_ENV."""
    env = os.getenv('FLASK_ENV', 'development').lower()
    config_class = config_by_name.get(env, config_by_name['default'])
    return config_class()
