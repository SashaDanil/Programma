import traceback
from datetime import datetime  # ✅ Правильный импорт
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from sqlalchemy import func, desc

from src.models import Review, NeuralResponse
from src.database import get_db
from src.scripts.FromatDate import format_datetime
from src.api.logger import logger
from src.schemas.ReviewWithResponse import ReviewWithResponseModel

router = APIRouter()

@router.get("/reviews_with_responses", response_model=dict, tags=["Отзывы"])
async def get_reviews_with_responses(
    limit: int = Query(100, gt=0, le=1000),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db)
):
    try:
        # Проверим, что datetime.fromisoformat доступен (для отладки)
        print("Check datetime.fromisoformat:", hasattr(datetime, 'fromisoformat'))  # Должно быть True

        total = db.query(func.count(Review.id)).join(
            NeuralResponse,
            Review.id == NeuralResponse.review_id
        ).scalar()

        reviews_data = db.query(
            Review.id.label("review_id"),
            Review.text.label("review_text"),
            NeuralResponse.response_text,
            NeuralResponse.created_at.label("response_created")
        ).join(
            NeuralResponse,
            Review.id == NeuralResponse.review_id
        ).order_by(
            desc(NeuralResponse.created_at)
        ).offset(offset).limit(limit).all()

        formatted_reviews = [{
            "review_id": row.review_id,
            "review_text": row.review_text,
            "response_text": row.response_text,
            "created_at": format_datetime(row.response_created)
        } for row in reviews_data]

        return {
            "data": formatted_reviews,
            "total": total,
            "limit": limit,
            "offset": offset
        }

    except Exception as e:
        logger.error(f"Error getting reviews: {e}\n{traceback.format_exc()}")
        raise HTTPException(status_code=500, detail=str(e))