from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from src.models import Review, NeuralResponse, Log
from src.database import get_db
from src.api.logger import logger
from src.rabbitmq_scripts.SendToRabbitMQ import send_to_rabbitmq

router = APIRouter()


@router.post("/send_all_error_reviews_to_queue", tags=["Отзывы"])

async def send_all_error_reviews_to_queue(
        db: Session = Depends(get_db)
):
    """
    Отправляет в RabbitMQ все отзывы со статусом 'InQueueError' (Ошибка очереди)
    """
    try:
        # Получаем все отзывы с ошибкой и их ответы
        error_reviews = db.query(
            Review,
            NeuralResponse.response_text,
            NeuralResponse.created_at
        ).join(
            NeuralResponse, Review.id == NeuralResponse.review_id
        ).filter(
            Review.status == "InQueueError"
        ).all()

        if not error_reviews:
            return {"status": "success", "count": 0, "message": "Нет отзывов с ошибкой для отправки"}

        success_count = 0
        failed_reviews = []

        for review_data in error_reviews:
            review, response_text, created_at = review_data

            try:
                # Форматируем дату (аналогично вашему коду)
                formatted_date = None
                if created_at:
                    if isinstance(created_at, str):
                        try:
                            dt = datetime.strptime(created_at, "%Y-%m-%d %H:%M:%S")
                            formatted_date = dt.isoformat()
                        except ValueError:
                            formatted_date = created_at
                    else:
                        formatted_date = created_at.isoformat()

                # Формируем сообщение
                message = {
                    "review_id": review.id,
                    "review_text": review.text,
                    "response_text": response_text,
                    "created_at": formatted_date,
                    "client_id": review.client_id
                }

                # Отправляем в RabbitMQ
                if not send_to_rabbitmq(message):
                    failed_reviews.append(review.id)
                    continue

                # Обновляем статус отзыва
                db.query(Review).filter(Review.id == review.id).update(
                    {"status": "InQueue"},
                    synchronize_session=False
                )

                # Логируем успешную отправку
                log_entry = Log(
                    timestamp=datetime.now(),
                    status="SENT_TO_QUEUE",
                    message=f"Review {review.id} resent to queue after error"
                )
                db.add(log_entry)

                success_count += 1

            except Exception as e:
                db.rollback()
                logger.error(f"Error processing review {review.id}: {str(e)}")
                failed_reviews.append(review.id)
                continue

        db.commit()

        result = {
            "status": "success",
            "count": success_count,
            "failed_count": len(failed_reviews),
            "failed_reviews": failed_reviews if failed_reviews else None,
            "message": f"Успешно отправлено {success_count} отзывов"
        }

        if failed_reviews:
            result["warning"] = f"Не удалось отправить {len(failed_reviews)} отзывов"

        return result

    except Exception as e:
        db.rollback()
        logger.error(f"Error in send_all_error_reviews_to_queue: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Ошибка при массовой отправке отзывов: {str(e)}"
        )