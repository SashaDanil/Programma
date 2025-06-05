import uuid
import re
from typing import Dict

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError

from src.models import ApiKeys
from src.schemas.api_key import ApiKeyCreate, ApiKeyUpdate, ApiKeyResponse
from src.database import get_db
from src.api.logger import logger

router = APIRouter(
    prefix="/CreateApi",
    tags=["API Keys Management"]
)

def contains_sql_injection(text: str) -> bool:
    """Проверяет строку на наличие SQL-инъекций"""
    sql_keywords = [
        'SELECT', 'INSERT', 'UPDATE', 'DELETE', 'DROP',
        'UNION', 'TRUNCATE', 'ALTER', 'CREATE', 'EXEC',
        '--', ';', '/*', '*/', 'OR 1=1', "'", '"', '`'
    ]
    pattern = re.compile('|'.join(re.escape(keyword) for keyword in sql_keywords), re.IGNORECASE)
    return bool(pattern.search(text))

def validate_input_data(data: ApiKeyCreate):
    """Валидирует входные данные на SQL-инъекции"""
    for field, value in data.model_dump().items():
        if isinstance(value, str) and contains_sql_injection(value):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Potential SQL injection detected in field '{field}'"
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


@router.post(
    "/",
    response_model=ApiKeyResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create new API key set"
)
async def create_api_key_set(
        api_key_data: ApiKeyCreate,
        db: Session = Depends(get_db)
) -> ApiKeyResponse:
    try:
        # Валидация входных данных
        validate_input_data(api_key_data)

        # Конвертация куков, если они есть
        api_key_dict = api_key_data.model_dump()
        if 'cookies' in api_key_dict and isinstance(api_key_dict['cookies'], dict):
            api_key_dict['cookies'] = convert_cookies_json_to_string(api_key_dict['cookies'])

        # Генерация UUID
        api_key_id = str(uuid.uuid4())
        new_key_set = ApiKeys(
            id=api_key_id,
            **api_key_dict
        )

        db.add(new_key_set)
        db.commit()
        db.refresh(new_key_set)

        logger.info(f"Created new API key set: {api_key_id}")
        return new_key_set

    except HTTPException:
        raise
    except IntegrityError:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="API key set already exists"
        )
    except Exception as e:
        db.rollback()
        logger.error(f"Error creating API keys: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to create API key set"
        )