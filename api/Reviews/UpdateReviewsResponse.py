import traceback
import re
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from datetime import datetime

from src.models import Review, NeuralResponse
from src.database import get_db
from src.schemas.UpdateResponseRequest import UpdateResponseRequestModel
from src.api.logger import logger

router = APIRouter()

def is_sql_injection(text: str) -> bool:
    """Проверяет, содержит ли текст SQL-инъекции."""
    sql_keywords = [
        'SELECT', 'INSERT', 'UPDATE', 'DELETE', 'DROP',
        'UNION', 'TRUNCATE', 'ALTER', 'CREATE', 'EXEC',
        '--', ';', '/*', '*/', 'OR 1=1'
    ]
    pattern = re.compile('|'.join(re.escape(keyword) for keyword in sql_keywords), re.IGNORECASE)
    return bool(pattern.search(text))

@router.put("/reviews/{review_id}/response", tags=["Отзывы"])
async def update_review_response(
        review_id: str,
        request: UpdateResponseRequestModel,
        db: Session = Depends(get_db)
):
    try:
        # Проверяем response_text на SQL-инъекции
        if is_sql_injection(request.response_text):
            raise HTTPException(status_code=400, detail="Potential SQL injection detected")

        # Проверяем существование отзыва
        review = db.query(Review).filter_by(id=review_id).first()
        if not review:
            raise HTTPException(status_code=404, detail="Review not found")

        # Ищем или создаем запись в neural_responses
        response = db.query(NeuralResponse).filter_by(review_id=review_id).first()

        if response:
            # Обновляем существующую запись
            response.response_text = request.response_text
            response.created_at = datetime.now()
        else:
            # Создаем новую запись
            response = NeuralResponse(
                review_id=review_id,
                response_text=request.response_text,
                created_at=datetime.now()
            )
            db.add(response)



        db.commit()
        return request.response_text

    except HTTPException:
        raise  # Пробрасываем HTTPException как есть
    except Exception as e:
        db.rollback()
        logger.error(f"Error updating response for review {review_id}: {str(e)}\n{traceback.format_exc()}")
        raise HTTPException(
            status_code=500,
            detail="Internal server error while updating response"
        )