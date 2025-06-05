import uuid
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from src.models import Prompt  # Импортируем модель
from src.schemas.Prompt import PromptModel
from src.schemas.PromptCreate import PromptCreateModel
from src.database import get_db
from src.api.logger import logger

router = APIRouter()


@router.post("/prompts", response_model=PromptModel, tags=["Общий промт"])
async def create_prompt(
        request: PromptCreateModel,
        db: Session = Depends(get_db)
):
    """Создать новый промт"""
    try:
        # Если новый промт активный, деактивируем другие
        if request.is_active:
            db.query(Prompt).update({"is_active": False})
            db.commit()

        # Создаем новый промт
        prompt = Prompt(
            id=str(uuid.uuid4()),
            content=request.content,
            is_active=request.is_active
        )

        db.add(prompt)
        db.commit()
        db.refresh(prompt)

        # Возвращаем созданный промт
        return {
            "id": prompt.id,
            "content": prompt.content,
            "is_active": prompt.is_active,
            "created_at": prompt.created_at.isoformat()
        }

    except Exception as e:
        db.rollback()
        logger.error(f"Error creating prompt: {str(e)}")
        raise HTTPException(status_code=500, detail="Internal server error")