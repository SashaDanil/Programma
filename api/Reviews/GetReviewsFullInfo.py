import traceback
from datetime import datetime
from typing import List

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session, joinedload
from sqlalchemy import desc, asc, func

from src.models import Review, ProductInfo, NeuralResponse, Photo, Video
from src.schemas.PaginatedResponse import PaginatedResponseModel
from src.database import get_db
from src.api.logger import logger


router = APIRouter()

@router.get("/reviews/full_info", response_model=PaginatedResponseModel, tags=["Отзывы"])
async def get_full_reviews_info(
    limit: int = Query(10, gt=0, le=100),
    offset: int = Query(0, ge=0),
    sort_by: str = Query("published_at"),
    sort_dir: str = Query("desc"),
    ozon_client_id: str = Query(None),
    sku: str = Query(None, description="Фильтр по SKU товара"),  # Добавлен новый параметр
    status: List[str] = Query(["UNPROCESSED"], description="Фильтр по статусам отзывов"),
    db: Session = Depends(get_db),
):
    try:
        # Валидация параметров сортировки
        sort_fields = {
            "published_at": Review.published_at,
            "rating": Review.rating,
            "product_name": ProductInfo.product_name
        }

        if sort_by not in sort_fields:
            sort_by = "published_at"

        sort_column = sort_fields[sort_by]
        sort_method = desc if sort_dir.lower() == "desc" else asc

        # Запрос для получения общего количества отзывов по статусам
        status_counts_query = db.query(
            Review.status,
            func.count(Review.id).label("count")
        ).group_by(Review.status)

        # Запрос для подсчета отзывов с ответами и без
        response_stats_query = db.query(
            func.count(Review.id).label("total"),
            func.count(NeuralResponse.id).label("with_response"),
            (func.count(Review.id) - func.count(NeuralResponse.id)).label("without_response")
        ).outerjoin(NeuralResponse, Review.id == NeuralResponse.review_id)

        if ozon_client_id:
            status_counts_query = status_counts_query.filter(Review.client_id == ozon_client_id)
            response_stats_query = response_stats_query.filter(Review.client_id == ozon_client_id)

        status_counts = {row.status: row.count for row in status_counts_query.all()}
        response_stats = response_stats_query.first()

        # Основной запрос с подгрузкой всех связанных данных
        query = db.query(Review).options(
            joinedload(Review.product_info),
            joinedload(Review.neural_response),
            joinedload(Review.photos),
            joinedload(Review.videos)
        ).filter(
            Review.status.in_(status)
        )

        # Добавляем фильтр по client_id, если он указан
        if ozon_client_id:
            query = query.filter(Review.client_id == ozon_client_id)

        # Если сортировка по product_name, добавляем JOIN
        if sort_by == "product_name":
            query = query.join(ProductInfo, Review.sku == ProductInfo.sku)

        if sku:
            query = query.filter(Review.sku == sku)

        # Сортировка
        query = query.order_by(sort_method(sort_column))

        # Пагинация
        total = query.count()
        results = query.offset(offset).limit(limit).all()

        reviews_data = []
        for review in results:
            # Формируем объект отзыва
            review_data = {
                "review_id": review.id,
                "client_id": review.client_id,
                "sku": review.sku,
                "product_name": review.product_info.product_name if review.product_info else f"Товар SKU: {review.sku}",
                "review_text": review.text or "Отзыв отсутствует",
                "rating": review.rating,
                "published_at": review.published_at,
                "status": review.status,
                "photos": [{
                    "url": p.url,
                    "width": p.width,
                    "height": p.height
                } for p in review.photos],
                "videos": [{
                    "url": v.url,
                    "preview_url": v.preview_url,
                    "short_video_preview_url": v.short_video_preview_url
                } for v in review.videos]
            }

            if review.neural_response:
                review_data["neural_response"] = {
                    "response_text": review.neural_response.response_text,
                    "created_at": review.neural_response.created_at
                }

            reviews_data.append(review_data)

        return {
            "data": reviews_data,
            "total": total,
            "limit": limit,
            "offset": offset,
            "status_counts": status_counts,
            "response_stats": {
                "total_reviews": response_stats.total,
                "with_response": response_stats.with_response,
                "without_response": response_stats.without_response
            }
        }

    except Exception as e:
        logger.error(f"Error getting reviews: {str(e)}\n{traceback.format_exc()}")
        raise HTTPException(status_code=500, detail=str(e))