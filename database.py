import psycopg2
from psycopg2 import OperationalError
from sqlalchemy import create_engine, text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker, Session
from fastapi import HTTPException
from contextlib import contextmanager
from typing import Generator
from datetime import datetime

from src.core_settings import DB_CONFIG, DATABASE_URL ,DATABASE_URL_asy # вместо своего импорта
from src.utils.logger import get_logger
from src.models import Log

# Инициализация логгера
logger = get_logger(__name__)

# Создание движка SQLAlchemy
engine = create_engine(DATABASE_URL, pool_pre_ping=True, pool_recycle=3600)

# Создание фабрики сессий
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

engine_async = create_async_engine(DATABASE_URL_asy, echo=True)

# Создание асинхронной сессии
async_session = sessionmaker(
    bind=engine_async,
    class_=AsyncSession,
    expire_on_commit=False
)

@contextmanager
def get_db_connection():
    """
    Контекстный менеджер для работы с соединением psycopg2.
    
    Yields:
        connection: Соединение с базой данных
    
    Raises:
        Exception: Если возникла ошибка подключения
    """
    conn = None
    try:
        conn = psycopg2.connect(**DB_CONFIG)
        yield conn
    except OperationalError as e:
        logger.error(f"Ошибка подключения к БД: {e}")
        raise Exception(f"Ошибка подключения к БД: {e}")
    finally:
        if conn:
            conn.close()

def log_to_db(status, message):
    """
    Добавляет запись в таблицу логов, используя SQLAlchemy ORM.
    
    Args:
        status: Статус операции
        message: Сообщение лога
    
    Raises:
        Exception: При ошибке записи в БД
    """
    try:
        # Создаем сессию
        db = SessionLocal()
        try:
            # Создаем новую запись лога
            log_entry = Log(
                timestamp=datetime.now().isoformat(),
                status=status,
                message=message
            )
            
            # Добавляем в сессию и сохраняем
            db.add(log_entry)
            db.commit()
            
            logger.debug(f"Записан лог: [{status}] {message}")
        except Exception as e:
            db.rollback()
            raise e
        finally:
            db.close()
    except Exception as e:
        logger.error(f"Ошибка записи лога в БД: {e}")
        raise Exception(f"Ошибка записи лога в БД: {e}")

def get_db() -> Generator[Session, None, None]:
    """
    Генератор сессий для FastAPI Depends.
    
    Yields:
        Session: Сессия базы данных SQLAlchemy
    
    Raises:
        HTTPException: При ошибке работы с БД
    """
    db = SessionLocal()
    try:
        logger.debug("Открыта новая сессия БД")
        yield db
    except SQLAlchemyError as e:
        db.rollback()
        logger.error(f"Ошибка базы данных: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Ошибка базы данных: {str(e)}")
    finally:
        logger.debug("Закрыта сессия БД")
        db.close()
