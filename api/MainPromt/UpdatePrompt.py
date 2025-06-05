from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from src.models import Prompt
from src.database import get_db
from src.schemas.Prompt import PromptModel
from src.schemas.PromptUpdate import PromptUpdateModel
from src.api.logger import logger

router = APIRouter()

@router.put("/prompts/{prompt_id}", response_model=PromptModel, tags=["Общий промт"])
async def update_prompt(
    prompt_id: str,
    request: PromptUpdateModel,
    db: Session = Depends(get_db)
):
    """Update prompt"""
    try:
        # Get the prompt or return 404
        prompt = db.query(Prompt).filter_by(id=prompt_id).first()
        if not prompt:
            raise HTTPException(status_code=404, detail="Prompt not found")

        # If activating this prompt, deactivate others
        if request.is_active is True:
            db.query(Prompt).filter(Prompt.is_active == True).update({"is_active": False})

        # Update fields if they're provided in request
        if request.content is not None:
            prompt.content = request.content
        if request.is_active is not None:
            prompt.is_active = request.is_active

        db.commit()
        db.refresh(prompt)  # Refresh to get updated values from DB

        return {
            "id": prompt.id,
            "content": prompt.content,
            "is_active": prompt.is_active,
            "created_at": prompt.created_at.isoformat()
        }

    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        logger.error(f"Error updating prompt {prompt_id}: {str(e)}")
        raise HTTPException(status_code=500, detail="Internal server error")