from datetime import datetime, timedelta
from fastapi import APIRouter, Query, HTTPException, Depends
from sqlalchemy.orm import Session
from sqlalchemy import func, and_
from typing import Optional

from src.database import get_db
from src.models import Review, ProductInfo
from src.api.logger import logger
import traceback

router = APIRouter()

@router.get("/reviews/product_report", tags=["Отчеты"])
async def get_product_reviews_report(
    sku: int = Query(..., description="SKU товара для отчета"),
    start_date: Optional[str] = Query(None, description="Начальная дата в формате YYYY-MM-DD"),
    end_date: Optional[str] = Query(None, description="Конечная дата в формате YYYY-MM-DD"),
    db: Session = Depends(get_db),
):
    """
    Получить отчет по отзывам для конкретного товара:
    - Общее количество отзывов
    - Средний рейтинг
    - Количество отзывов по каждому рейтингу
    - Количество отзывов с фото/видео
    - Динамика отзывов по датам (количество и средний рейтинг)
    - Общее количество отзывов за все время
    """
    try:
        # Базовый запрос с фильтром по SKU
        base_query = db.query(Review).join(
            ProductInfo, Review.id == ProductInfo.review_id
        ).filter(
            ProductInfo.sku == sku
        )

        # Получаем общее количество отзывов за ВСЕ время (без учета дат)
        total_all_time = db.query(Review).join(
            ProductInfo, Review.id == ProductInfo.review_id
        ).filter(
            ProductInfo.sku == sku
        ).count()

        # Применяем фильтры по дате, если они указаны
        if start_date:
            try:
                start_datetime = datetime.strptime(start_date, "%Y-%m-%d")
                base_query = base_query.filter(Review.published_at >= start_datetime)
            except ValueError:
                raise HTTPException(status_code=400, detail="Неверный формат start_date. Используйте YYYY-MM-DD")

        if end_date:
            try:
                end_datetime = datetime.strptime(end_date, "%Y-%m-%d") + timedelta(days=1)
                base_query = base_query.filter(Review.published_at < end_datetime)
            except ValueError:
                raise HTTPException(status_code=400, detail="Неверный формат end_date. Используйте YYYY-MM-DD")

        # Получаем общее количество отзывов за период
        total_reviews = base_query.count()

        # Если нет отзывов, возвращаем пустой отчет
        if total_reviews == 0:
            return {
                "sku": sku,
                "total_reviews": 0,
                "total_all_time": total_all_time,
                "average_rating": 0,
                "rating_distribution": {},
                "reviews_with_photos": 0,
                "reviews_with_videos": 0,
                "reviews_by_date": {},
                "period": {
                    "start_date": start_date,
                    "end_date": end_date
                }
            }

        # Получаем средний рейтинг
        average_rating = db.query(
            func.avg(Review.rating).label("average_rating")
        ).join(
            ProductInfo, Review.id == ProductInfo.review_id
        ).filter(
            ProductInfo.sku == sku
        )

        if start_date:
            average_rating = average_rating.filter(Review.published_at >= start_datetime)
        if end_date:
            average_rating = average_rating.filter(Review.published_at < end_datetime)

        average_rating = average_rating.scalar() or 0

        # Получаем распределение по рейтингам
        rating_distribution = db.query(
            Review.rating,
            func.count(Review.id).label("count")
        ).join(
            ProductInfo, Review.id == ProductInfo.review_id
        ).filter(
            ProductInfo.sku == sku
        )

        if start_date:
            rating_distribution = rating_distribution.filter(Review.published_at >= start_datetime)
        if end_date:
            rating_distribution = rating_distribution.filter(Review.published_at < end_datetime)

        rating_distribution = rating_distribution.group_by(Review.rating).all()
        rating_distribution = {str(rating): count for rating, count in rating_distribution}

        # Получаем количество отзывов с фото
        reviews_with_photos = base_query.filter(
            Review.photos.any()
        ).count()

        # Получаем количество отзывов с видео
        reviews_with_videos = base_query.filter(
            Review.videos.any()
        ).count()

        # Получаем динамику отзывов по датам (количество + средний рейтинг)
        reviews_by_date_query = db.query(
            func.date(Review.published_at).label("date"),
            func.count(Review.id).label("count"),
            func.avg(Review.rating).label("avg_rating")
        ).join(
            ProductInfo, Review.id == ProductInfo.review_id
        ).filter(
            ProductInfo.sku == sku
        )

        if start_date:
            reviews_by_date_query = reviews_by_date_query.filter(Review.published_at >= start_datetime)
        if end_date:
            reviews_by_date_query = reviews_by_date_query.filter(Review.published_at < end_datetime)

        reviews_by_date = reviews_by_date_query.group_by(
            func.date(Review.published_at)
        ).order_by(
            func.date(Review.published_at)
        ).all()

        # Преобразуем в словарь с датами в формате строк
        reviews_by_date_dict = {
            date.strftime("%Y-%m-%d"): {
                "count": count,
                "avg_rating": round(float(avg_rating), 2) if avg_rating else 0
            }
            for date, count, avg_rating in reviews_by_date
        }

        return {
            "sku": sku,
            "total_reviews": total_reviews,
            "total_all_time": total_all_time,
            "average_rating": round(float(average_rating), 2),
            "rating_distribution": rating_distribution,
            "reviews_with_photos": reviews_with_photos,
            "reviews_with_videos": reviews_with_videos,
            "reviews_by_date": reviews_by_date_dict,
            "period": {
                "start_date": start_date,
                "end_date": end_date
            }
        }

    except Exception as e:
        logger.error(f"Error generating product report: {str(e)}\n{traceback.format_exc()}")
        raise HTTPException(status_code=500, detail=str(e))