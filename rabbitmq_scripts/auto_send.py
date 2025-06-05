import asyncio
import logging
from datetime import datetime
from sqlalchemy import select, update, and_, or_
from sqlalchemy.ext.asyncio import AsyncSession

from src.models import Review, NeuralResponse, Log, ReviewFilter
from src.rabbitmq_scripts.SendToRabbitMQ import send_to_rabbitmq
from src.utils.logger import get_logger

logger = get_logger(__name__)


def format_datetime(dt):
    """Форматируем datetime в строку для БД"""
    if isinstance(dt, str):
        return dt  # уже строка, возвращаем как есть
    return dt.isoformat() if dt else None


async def get_active_filters(session: AsyncSession):
    """Получаем активные фильтры из БД"""
    result = await session.execute(
        select(ReviewFilter).where(ReviewFilter.IS_ACTIVE == True)
    )
    return result.scalars().all()


async def get_filtered_reviews(session: AsyncSession, filter):
    """Получаем отзывы по фильтру"""
    query = select(
        Review,
        NeuralResponse.response_text,
        NeuralResponse.created_at
    ).join(
        NeuralResponse, Review.id == NeuralResponse.review_id
    ).where(
        Review.status == "UNPROCESSED",
    )

    if filter.RATING is not None:
        query = query.where(Review.rating == filter.RATING)

    if filter.HAS_TEXT is not None:
        if filter.HAS_TEXT:
            query = query.where(and_(
                Review.text.is_not(None),
                Review.text != ""
            ))
        else:
            query = query.where(or_(
                Review.text.is_(None),
                Review.text == ""
            ))

    result = await session.execute(query)
    return result.all()


async def send_review_to_queue(session: AsyncSession, review, response_text, created_at, filter_id):
    try:
        message = {
            "review_id": review.id,
            "review_text": review.text,
            "response_text": response_text,
            "created_at": format_datetime(created_at),
            "client_id": review.client_id,
            "filter_id": filter_id
        }

        logger.debug(f"Preparing to send message: {message}")

        # Отправка в RabbitMQ
        loop = asyncio.get_event_loop()
        success = await loop.run_in_executor(None, send_to_rabbitmq, message)

        if not success:
            logger.error(f"Failed to send message for review {review.id}")
            return False

        # Обновляем статус отзыва
        await session.execute(
            update(Review)
            .where(Review.id == review.id)
            .values(status="InQueue")
        )

        # Логируем действие
        log_entry = Log(
            timestamp=datetime.now().isoformat(),
            status="SENT_TO_QUEUE",
            message=f"Review {review.id} sent via filter {filter_id}"
        )
        session.add(log_entry)

        await session.commit()
        logger.debug(f"Successfully processed review {review.id}")

        return True

    except Exception as e:
        await session.rollback()
        logger.error(f"Error sending review {review.id}: {str(e)}", exc_info=True)
        return False


async def send_filtered_reviews(session: AsyncSession):
    try:
        # Явный запрос фильтров
        stmt = select(ReviewFilter).where(ReviewFilter.IS_ACTIVE == True)
        result = await session.execute(stmt)
        filters = result.scalars().all()

        if not filters:
            logger.debug("No active filters found")
            return 0

        total_sent = 0

        for filter in filters:
            # Правильное построение условий
            conditions = [Review.status == "UNPROCESSED"]

            if filter.RATING is not None:
                conditions.append(Review.rating == filter.RATING)

            if filter.HAS_TEXT is False:
                conditions.append(or_(Review.text.is_(None), Review.text == ""))
            elif filter.HAS_TEXT is True:
                conditions.append(Review.text.is_not(None))
                conditions.append(Review.text != "")

            # Выполняем запрос
            reviews_stmt = select(
                Review,
                NeuralResponse.response_text,
                NeuralResponse.created_at
            ).join(
                NeuralResponse,
                Review.id == NeuralResponse.review_id
            ).where(*conditions)

            reviews_result = await session.execute(reviews_stmt)
            reviews = reviews_result.all()

            for review, response_text, created_at in reviews:
                if await send_review_to_queue(session, review, response_text, created_at, filter.id):
                    total_sent += 1

        logger.info(f"Sent {total_sent} reviews to queue")
        return total_sent

    except Exception as e:
        logger.error(f"Error in send_filtered_reviews: {str(e)}", exc_info=True)
        raise  # Пробрасываем исключение выше