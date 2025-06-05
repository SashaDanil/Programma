import uuid
import re
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError

from src.models import ReviewFilter
from src.schemas.review_filter import ReviewFilterCreate, ReviewFilterUpdate, ReviewFilterResponse
from src.database import get_db
from src.api.logger import logger

router = APIRouter(
    prefix="/review-filters",
    tags=["Review Filters Management"]
)

def contains_sql_injection(text: str) -> bool:
    """Проверяет строку на наличие SQL-инъекций"""
    sql_keywords = [
        'SELECT', 'INSERT', 'UPDATE', 'DELETE', 'DROP',
        'UNION', 'TRUNCATE', 'ALTER', 'CREATE', 'EXEC',
        '--', ';', '/*', '*/', 'OR 1=1', "'", '"', '`'
    ]
    pattern = re.compile('|'.join(re.escape(keyword) for keyword in sql_keywords), re.IGNORECASE)
    return bool(pattern.search(text))

def validate_input_data(data):
    """Валидирует входные данные на SQL-инъекции"""
    for field, value in data.model_dump().items():
        if isinstance(value, str) and contains_sql_injection(value):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Potential SQL injection detected in field '{field}'"
            )


@router.delete(
    "/{filter_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete review filter (soft delete by default)"
)
async def delete_review_filter(
    filter_id: str,
    hard_delete: bool = False,
    db: Session = Depends(get_db)
):
    try:
        # Получаем фильтр из базы данных
        db_filter = db.query(ReviewFilter).filter(ReviewFilter.id == filter_id).first()
        if not db_filter:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Review filter not found"
            )

        if hard_delete:
            # Полное удаление из базы данных
            db.delete(db_filter)
            logger.info(f"Hard deleted review filter: {filter_id}")
        else:
            # Мягкое удаление (установка IS_ACTIVE=False)
            db_filter.IS_ACTIVE = False
            logger.info(f"Soft deleted review filter: {filter_id}")

        db.commit()

    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        logger.error(f"Error deleting review filter: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to delete review filter"
        )