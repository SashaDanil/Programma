from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import func, desc
from datetime import datetime

from src.models import ProductPrompt, ProductInfo
from src.database import get_db
from src.schemas.ProductPromptResponse import ProductPromptResponseModel

router = APIRouter()


@router.get("/product_prompts", response_model=list[ProductPromptResponseModel], tags=["Промты товаров"])
async def list_product_prompts(
        skip: int = 0,
        limit: int = 100,
        db: Session = Depends(get_db)
):
    try:
        # Подзапрос для product_name
        product_name_subquery = db.query(
            ProductInfo.sku,
            func.max(ProductInfo.product_name).label('product_name')
        ).group_by(ProductInfo.sku).subquery()

        # Основной запрос
        prompts = db.query(
            ProductPrompt.sku,
            ProductPrompt.prompt,
            product_name_subquery.c.product_name,
            ProductPrompt.updated_at
        ).outerjoin(
            product_name_subquery,
            ProductPrompt.sku == product_name_subquery.c.sku
        ).order_by(
            desc(ProductPrompt.updated_at)
        ).offset(skip).limit(limit).all()

        # Преобразуем в формат для Pydantic
        result = []
        for p in prompts:
            # Конвертируем updated_at в datetime, если нужно
            updated_at = p.updated_at
            if isinstance(updated_at, str):
                try:
                    updated_at = datetime.fromisoformat(updated_at)
                except ValueError:
                    updated_at = datetime.strptime(updated_at, '%Y-%m-%d %H:%M:%S')

            result.append({
                "sku": str(p.sku),  # Конвертируем в строку, как требует схема
                "prompt": p.prompt,
                "product_name": p.product_name,
                "updated_at": updated_at
            })

        return result

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))