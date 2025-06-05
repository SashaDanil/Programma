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


@router.post(
    "/",
    response_model=ReviewFilterResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create new review filter"
)
async def create_review_filter(
    filter_data: ReviewFilterCreate,
    db: Session = Depends(get_db)
) -> ReviewFilterResponse:
    try:
        # Валидация входных данных
        validate_input_data(filter_data)

        # Генерация UUID
        filter_id = str(uuid.uuid4())
        new_filter = ReviewFilter(
            id=filter_id,
            **filter_data.model_dump()
        )

        db.add(new_filter)
        db.commit()
        db.refresh(new_filter)

        logger.info(f"Created new review filter: {filter_id}")
        return new_filter

    except HTTPException:
        raise
    except IntegrityError:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Review filter with this ID already exists"
        )
    except Exception as e:
        db.rollback()
        logger.error(f"Error creating review filter: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to create review filter"
        )