from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from src.models import Review, NeuralResponse, Log
from src.database import get_db
from src.api.logger import logger
from src.rabbitmq_scripts.SendToRabbitMQ import send_to_rabbitmq

router = APIRouter()

@router.post("/send_specific_review", tags=["Отзывы"])
async def send_specific_review(
    review_id: str,
    db: Session = Depends(get_db)
):
    """
    Отправляет в RabbitMQ конкретный отзыв по его ID
    """
    try:
        # Ищем отзыв с ответом нейросети
        review_data = db.query(
            Review,
            NeuralResponse.response_text,
            NeuralResponse.created_at
        ).join(
            NeuralResponse, Review.id == NeuralResponse.review_id
        ).filter(
            Review.id == review_id
        ).first()

        if not review_data:
            raise HTTPException(status_code=404, detail="Отзыв с ответом не найден")

        review, response_text, created_at = review_data

        # Форматируем дату (исправление ошибки)
        formatted_date = None
        if created_at:
            if isinstance(created_at, str):
                # Если created_at строка - преобразуем в datetime
                try:
                    dt = datetime.strptime(created_at, "%Y-%m-%d %H:%M:%S")  # Или другой формат
                    formatted_date = dt.isoformat()
                except ValueError:
                    formatted_date = created_at  # Оставляем как есть если не парсится
            else:
                # Если это уже datetime объект
                formatted_date = created_at.isoformat()

        # Формируем сообщение
        message = {
            "review_id": review.id,
            "review_text": review.text,
            "response_text": response_text,
            "created_at": formatted_date,
            "client_id":review.client_id
        }

        # Отправляем в RabbitMQ
        if not send_to_rabbitmq(message):
            raise HTTPException(status_code=500, detail="Ошибка отправки в очередь")

        try:
            db.query(Review).filter(Review.id == review_id).update(
                {"status": "InQueue"},
                synchronize_session=False
            )
            db.commit()
        except Exception as e:
            db.rollback()
            logger.error(f"Ошибка обновления статуса: {str(e)}")
            raise

        # Логируем успешную отправку
        log_entry = Log(
            timestamp=datetime.now(),
            status="SENT_TO_QUEUE",
            message=f"Review {review.id} sent to queue manually"
        )
        db.add(log_entry)
        db.commit()

        return {"status": "success", "message": "Отзыв отправлен в очередь"}

    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        logger.error(f"Error sending review {review_id}: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))