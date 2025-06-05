import uuid
from typing import Dict

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError

from src.models import ApiKeys
from src.schemas.api_key import ApiKeyCreate, ApiKeyUpdate, ApiKeyResponse
from src.database import get_db
from src.api.logger import logger

router = APIRouter(
    prefix="/UpdateApi",
    tags=["API Keys Management"]
)


def convert_cookies_json_to_string(cookies_json: Dict[str, str]) -> str:
    """
    Конвертирует куки из JSON-формата в строку формата "key=value; key2=value2"

    Args:
        cookies_json: Словарь с куками, например {'cf_clearance': 'value', '__Secure-ab-group': '61'}

    Returns:
        Строка с куками в формате для хранения в БД, например "cf_clearance=value; __Secure-ab-group=61"
    """
    return "; ".join(f"{k}={v}" for k, v in cookies_json.items())

@router.put(
    "/{key_id}",
    response_model=ApiKeyResponse,
    summary="Update API key set"
)
async def update_api_key(
        key_id: str,
        api_key_data: ApiKeyUpdate,
        db: Session = Depends(get_db)
) -> ApiKeyResponse:
    try:
        key_set = db.query(ApiKeys).filter(ApiKeys.id == key_id).first()
        if not key_set:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="API key set not found"
            )

        update_data = api_key_data.model_dump(exclude_unset=True)

        # Конвертация куков, если они есть в обновлении
        if 'cookies' in update_data and isinstance(update_data['cookies'], dict):
            update_data['cookies'] = convert_cookies_json_to_string(update_data['cookies'])

        for field, value in update_data.items():
            setattr(key_set, field, value)

        db.commit()
        db.refresh(key_set)

        logger.info(f"Updated API key set: {key_id}")
        return key_set

    except Exception as e:
        db.rollback()
        logger.error(f"Error updating API keys: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to update API key set"
        )