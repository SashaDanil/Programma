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


@router.get(
    "/",
    response_model=list[ReviewFilterResponse],
    status_code=status.HTTP_200_OK,
    summary="Get all review filters"
)
async def get_all_review_filters(
    db: Session = Depends(get_db)
) -> list[ReviewFilterResponse]:
    try:
        filters = db.query(ReviewFilter).all()
        return filters
    except Exception as e:
        logger.error(f"Error fetching review filters: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to fetch review filters"
        )
