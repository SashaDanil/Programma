import traceback
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import Dict, Any

from src.models import (
    Review,
    ProductInfo,
    NeuralResponse,
    LogsNeuro
)
from src.database import get_db
from src.utils.logger import get_logger
from src.neural.neural_network import get_gpt_response

# Инициализация логгера
logger = get_logger(__name__)

# Создание роутера
router = APIRouter()

# Тексты для замены пустых отзывов
RATING_TEXTS = {
    1: "Товар ужасный, не рекомендую.",
    2: "Товар плохой, есть много недостатков.",
    3: "Товар средний, есть как плюсы, так и минусы.",
    4: "Товар хороший, рекомендую.",
    5: "Товар отличный, полностью удовлетворен покупкой."
}

@router.post("/process_unprocessed_reviews", tags=["Отзывы"])
async def process_unprocessed_reviews(db: Session = Depends(get_db)) -> Dict[str, Any]:
    """
    Обрабатывает отзывы без ответов нейронной сетью.
    
    Args:
        db: Сессия базы данных
        
    Returns:
        Dict[str, Any]: Результат обработки
        
    Raises:
        HTTPException: При ошибке обработки
    """
    try:
        logger.info("Начало обработки отзывов без ответов")

        # Получаем отзывы без ответов
        query = (
            db.query(Review, ProductInfo)
            .outerjoin(ProductInfo, Review.id == ProductInfo.review_id)
            .outerjoin(NeuralResponse, Review.id == NeuralResponse.review_id)
            .filter(NeuralResponse.id == None)  # Берем только отзывы без ответа
            .limit(100)
        )
        
        # Выполняем запрос
        reviews = query.all()

        if not reviews:
            logger.info("Нет отзывов без ответов для обработки")
            return {"message": "Нет отзывов без ответов для обработки."}

        processed_count = 0
        errors_count = 0

        # Обрабатываем каждый отзыв
        for review, product_info in reviews:
            try:
                logger.info(f"Обработка отзыва ID: {review.id}")

                # Определяем текст для отправки в нейросеть
                review_text = review.text if review.text else f"Рейтинг: {review.rating}/5"
                
                # Получаем название продукта
                product_name = product_info.product_name if product_info else None
                # Генерация ответа нейросетью
                neural_response = get_gpt_response(
                    review_text=review_text,
                    db=db,
                    product_name=product_name,
                    sku=review.sku,
                    rating=review.rating
                )

                # Проверяем ответ нейросети
                if not neural_response or not neural_response.strip():
                    raise ValueError("Нейросеть не вернула валидный ответ")

                # Создаем запись ответа
                now = datetime.now()
                
                # Создаем объект ответа
                new_response = NeuralResponse(
                    review_id=review.id,
                    response_text=neural_response,
                    created_at=now.isoformat()
                )
                
                # Создаем запись лога
                log_entry = LogsNeuro(
                    review_text=review_text[:500],
                    response_text=neural_response,
                    status='SUCCESS',
                    created_at=now.isoformat()
                )
                
                # Добавляем в сессию и сохраняем
                db.add(new_response)
                db.add(log_entry)
                db.commit()
                
                processed_count += 1
                logger.info(f"Успешно обработан отзыв ID: {review.id}")

            except Exception as e:
                # Откатываем транзакцию
                db.rollback()
                
                # Логируем ошибку
                error_msg = f"Ошибка обработки отзыва ID {review.id}: {str(e)}"
                logger.error(error_msg)
                
                # Создаем запись об ошибке
                db.add(LogsNeuro(
                    review_text=review.text[:500] if review.text else f"Рейтинг: {review.rating}/5",
                    response_text=str(e)[:500],
                    status="ERROR",
                    created_at=datetime.now().isoformat()
                ))
                db.commit()
                
                errors_count += 1

        # Возвращаем результат
        return {
            "message": "Обработка завершена",
            "processed": processed_count,
            "errors": errors_count
        }

    except Exception as e:
        # Логируем критическую ошибку
        error_details = f"Критическая ошибка: {str(e)}\n{traceback.format_exc()}"
        logger.error(error_details)
        
        # Возвращаем HTTP ошибку
        raise HTTPException(status_code=500, detail=str(e))