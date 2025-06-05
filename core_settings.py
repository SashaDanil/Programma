# core_settings.py
import os
from pathlib import Path

BASE_DIR = Path(__file__).parent.parent
SRC_DIR = Path(__file__).parent

# Настройки приложения
DEBUG = os.getenv("DEBUG", "False").lower() == "true"
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")

# Настройки БД (если нужны)
DB_CONFIG = {
    'dbname': os.getenv('POSTGRES_DB', 'reviews'),
    'user': os.getenv('POSTGRES_USER', 'Ilya'),
    'password': os.getenv('POSTGRES_PASSWORD', 'ilyailya228'),
    'host': os.getenv('POSTGRES_HOST', '94.181.95.99'),
    'port': os.getenv('POSTGRES_PORT', '5432')
}
DATABASE_URL = f"postgresql://{DB_CONFIG['user']}:{DB_CONFIG['password']}@{DB_CONFIG['host']}:{DB_CONFIG['port']}/{DB_CONFIG['dbname']}"
DATABASE_URL_asy = f"postgresql+asyncpg://{DB_CONFIG['user']}:{DB_CONFIG['password']}@{DB_CONFIG['host']}:{DB_CONFIG['port']}/{DB_CONFIG['dbname']}"