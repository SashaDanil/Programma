from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from sqlalchemy import func

from src.models import ProductPrompt, ProductInfo
from src.database import get_db
from src.api.logger import logger
from src.schemas.ProductPromptResponse import ProductPromptResponseModel

router = APIRouter()

@router.get("/product_prompts/search", response_model=ProductPromptResponseModel, tags=["Промты товаров"])
async def search_product_prompts(
    sku: str = Query(..., description="SKU товара для поиска"),
    db: Session = Depends(get_db)
):
    """
    Поиск промтов товаров по SKU (точное совпадение)
    """
    try:
        # Создаем подзапрос для получения product_name
        product_name_subquery = db.query(
            ProductInfo.sku,
            func.max(ProductInfo.product_name).label('product_name')
        ).filter(
            ProductInfo.sku == sku
        ).group_by(
            ProductInfo.sku
        ).subquery()

        # Основной запрос
        prompt = db.query(
            ProductPrompt.sku,
            ProductPrompt.prompt,
            product_name_subquery.c.product_name,
            ProductPrompt.updated_at
        ).outerjoin(
            product_name_subquery,
            ProductPrompt.sku == product_name_subquery.c.sku
        ).filter(
            ProductPrompt.sku == sku
        ).first()

        if not prompt:
            raise HTTPException(
                status_code=404,
                detail=f"Промт для товара с SKU {sku} не найден"
            )

        # Преобразуем результат в формат, ожидаемый схемой
        return {
            "sku": str(prompt.sku),  # Явно преобразуем в строку
            "prompt": prompt.prompt,
            "product_name": prompt.product_name,
            "updated_at": prompt.updated_at
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Ошибка поиска промта: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail="Произошла ошибка при поиске промта"
        )