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


@router.patch(
    "/{filter_id}",
    response_model=ReviewFilterResponse,
    status_code=status.HTTP_200_OK,
    summary="Update review filter"
)
async def update_review_filter(
    filter_id: str,
    filter_data: ReviewFilterUpdate,
    db: Session = Depends(get_db)
) -> ReviewFilterResponse:
    try:
        # Валидация входных данных
        validate_input_data(filter_data)

        # Получаем фильтр из базы данных
        db_filter = db.query(ReviewFilter).filter(ReviewFilter.id == filter_id).first()
        if not db_filter:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Review filter not found"
            )

        # Обновляем только переданные поля
        update_data = filter_data.model_dump(exclude_unset=True)
        for field, value in update_data.items():
            setattr(db_filter, field, value)

        db.commit()
        db.refresh(db_filter)

        logger.info(f"Updated review filter: {filter_id}")
        return db_filter

    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        logger.error(f"Error updating review filter: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to update review filter"
        )