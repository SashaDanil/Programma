from fastapi import APIRouter, Depends, HTTPException, Form
from sqlalchemy.orm import Session
from sqlalchemy.dialects.postgresql import insert

from src.models import ProductPrompt, ProductInfo
from src.database import get_db

router = APIRouter()

@router.post("/update_product_prompt", tags=["Промты товаров"])
async def update_product_prompt(
    sku: int = Form(...),
    prompt: str = Form(None),
    db: Session = Depends(get_db)
):
    try:
        # Проверяем существование SKU
        if not db.query(ProductInfo.sku).filter_by(sku=sku).first():
            raise HTTPException(status_code=404, detail="SKU не найден")

        # Создаем или обновляем промпт
        stmt = insert(ProductPrompt).values(
            sku=sku,
            prompt=prompt
        ).on_conflict_do_update(
            index_elements=['sku'],
            set_={'prompt': prompt}
        )

        db.execute(stmt)
        db.commit()

        return {
            "message": "Промпт обновлен",
            "sku": sku,
            "prompt": prompt
        }

    except HTTPException:
        raise  # Пробрасываем HTTPException как есть

    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=500,
            detail=f"Ошибка при обновлении промпта: {str(e)}"
        )