import os
from dotenv import load_dotenv
import logging
from datetime import datetime, timedelta

load_dotenv()

class Config:
    # Backend specific configs
    FLASK_HOST = os.getenv('FLASK_HOST')
    FLASK_PORT = int(os.getenv('FLASK_PORT'))
    FLASK_DEBUG = os.getenv('FLASK_DEBUG', 'False').lower()
    
    # Google OAuth configs (moved to backend)
    GOOGLE_CLIENT_ID = os.getenv('GOOGLE_CLIENT_ID')
    GOOGLE_CLIENT_SECRET = os.getenv('GOOGLE_CLIENT_SECRET')
    GOOGLE_DISCOVERY_URL = "https://accounts.google.com/.well-known/openid-configuration"
    CallbackUrl = os.getenv('CallbackUrl')
    
    # Domain Checking Configuration
    MAX_WORKERS = int(os.getenv('MAX_WORKERS'))
    HTTP_TIMEOUT = int(os.getenv('HTTP_TIMEOUT'))
    SSL_TIMEOUT = int(os.getenv('SSL_TIMEOUT'))
    OVERALL_CHECK_TIMEOUT = int(os.getenv('OVERALL_CHECK_TIMEOUT'))
    
    # File Storage Configuration
    JSON_DIRECTORY = os.getenv('JSON_DIRECTORY')
    LOGS_DIRECTORY = os.getenv('LOGS_DIRECTORY')
    
    # Logging Configuration
    LOG_LEVEL = os.getenv('LOG_LEVEL', 'INFO')
    LOG_FORMAT = '%(asctime)s - %(levelname)s - %(message)s'
    LOG_DATE_FORMAT = '%Y-%m-%d %H:%M:%S'
    DEBUG_LOG_FORMAT = '%(asctime)s - DEBUG - [%(filename)s:%(lineno)d] - %(funcName)s - %(message)s'
    ERROR_LOG_FORMAT = '%(asctime)s - %(levelname)s - [%(filename)s:%(lineno)d] - %(message)s\n%(exc_info)s'
    
    # CORS Configuration
    CORS_ALLOWED_ORIGINS = os.getenv('CORS_ALLOWED_ORIGINS').split(',')

    # elastic apm configuration
    SECRET_TOKEN = os.getenv('SECRET_TOKEN')
    SERVER_URL = os.getenv('SERVER_URL')


def setup_logger():
    """Setup logger with daily files for the backend service"""
    if not os.path.exists(Config.LOGS_DIRECTORY):
        os.makedirs(Config.LOGS_DIRECTORY)
    
    logger = logging.getLogger('domain_monitor')
    logger.setLevel(getattr(logging, Config.LOG_LEVEL))
    logger.handlers = []
    
    current_date = datetime.now().strftime("%Y%m%d")
    
    # App log file (INFO and higher)
    app_handler = logging.FileHandler(f'{Config.LOGS_DIRECTORY}/app_{current_date}.log')
    app_handler.setLevel(logging.INFO)
    app_handler.setFormatter(logging.Formatter(
        Config.LOG_FORMAT,
        datefmt=Config.LOG_DATE_FORMAT
    ))
    
    # Debug log file
    debug_handler = logging.FileHandler(f'{Config.LOGS_DIRECTORY}/debug_{current_date}.log')
    debug_handler.setLevel(logging.DEBUG)
    debug_handler.addFilter(lambda record: record.levelno == logging.DEBUG)
    debug_handler.setFormatter(logging.Formatter(
        Config.DEBUG_LOG_FORMAT,
        datefmt=Config.LOG_DATE_FORMAT
    ))
    
    # Error log file
    error_handler = logging.FileHandler(f'{Config.LOGS_DIRECTORY}/error_{current_date}.log')
    error_handler.setLevel(logging.ERROR)
    error_handler.setFormatter(logging.Formatter(
        Config.ERROR_LOG_FORMAT,
        datefmt=Config.LOG_DATE_FORMAT
    ))

    # Console handler (INFO and higher for cleaner console)
    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.DEBUG)
    console_handler.setFormatter(logging.Formatter('%(levelname)s - %(message)s'))
    
    logger.addHandler(app_handler)
    logger.addHandler(debug_handler)
    logger.addHandler(error_handler)
    logger.addHandler(console_handler)
    
    return logger

# Create logger instance
logger = setup_logger()