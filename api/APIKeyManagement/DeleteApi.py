
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from src.models import ApiKeys
from src.database import get_db
from src.api.logger import logger

router = APIRouter(
    prefix="/DeliteApi",
    tags=["API Keys Management"]
)

@router.delete(
    "/{key_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete API key set"
)
async def delete_api_key(
    key_id: str,
    db: Session = Depends(get_db)
):
    try:
        key_set = db.query(ApiKeys).filter(ApiKeys.id == key_id).first()
        if not key_set:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="API key set not found"
            )

        db.delete(key_set)
        db.commit()
        logger.info(f"Deleted API key set: {key_id}")

    except Exception as e:
        db.rollback()
        logger.error(f"Error deleting API keys: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to delete API key set"
        )