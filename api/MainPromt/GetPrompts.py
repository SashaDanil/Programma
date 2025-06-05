from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import desc

from src.database import get_db
from src.models import Prompt  # Импортируем модель
from src.schemas.Prompt import PromptModel
from src.api.logger import logger

router = APIRouter()


@router.get("/prompts", response_model=list[PromptModel], tags=["Общий промт"])
async def get_prompts(db: Session = Depends(get_db)):
    """Получить все промты (сортировка: активные сначала)"""
    try:
        prompts = db.query(Prompt).order_by(
            desc(Prompt.is_active),  # Сначала активные
            desc(Prompt.created_at)  # Потом новые
        ).all()

        return [
            {
                "id": prompt.id,
                "content": prompt.content,
                "is_active": prompt.is_active,
                "created_at": prompt.created_at.isoformat()
            }
            for prompt in prompts
        ]
    except Exception as e:
        logger.error(f"Error getting prompts: {str(e)}")
        raise HTTPException(status_code=500, detail="Internal server error")