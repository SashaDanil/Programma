import uuid
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError

from src.models import ApiKeys
from src.schemas.api_key import ApiKeyCreate, ApiKeyUpdate, ApiKeyResponse
from src.database import get_db
from src.api.logger import logger

router = APIRouter(
    prefix="/GetApi",
    tags=["API Keys Management"]
)

@router.get(
    "/",
    response_model=list[ApiKeyResponse],
    summary="Get all API key sets"
)
async def get_all_api_keys(
    db: Session = Depends(get_db)
) -> list[ApiKeyResponse]:
    try:
        keys = db.query(ApiKeys).all()
        return keys
    except Exception as e:
        logger.error(f"Error fetching API keys: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to fetch API keys"
        )