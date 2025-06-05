from pydantic import BaseModel, Field
from typing import Optional

class ApiKeyBase(BaseModel):
    yandex_gpt_folder: Optional[str] = Field(
        None,
        description="Yandex GPT FOLDER",
        example="b1g54ufj135u901su5ju"
    )
    YANDEX_GPT_API_KEY: Optional[str] = Field(
        None,
        description="Yandex GPT API key",
        example="AQVN1xmJtqS4RkHgXkXvXeXi5HgY5rFg1"
    )
    OZON_API_KEY: Optional[str] = Field(
        None,
        description="Ozon Seller API key",
        example="a1b2c3d4-e5f6-g7h8-i9j0-k1l2m3n4o5p6"
    )
    OZON_CLIENT_ID: Optional[str] = Field(
        None,
        description="Ozon Client ID",
        example="123456"
    )
    LAST_ID: Optional[str] = Field(
        None,
        description="LAST ID",
        example="123456"
    )
    TIMESTUMP: Optional[str] = Field(  # Оставлено как есть
        None,
        description="Timestamp of the last update",
        example="2023-10-01T12:00:00Z"
    )
    IS_PREMIUM_PLUS: Optional[bool] = Field(
        True,
        description="Check for Premium Plus subscription",
        example=True
    )
    OZON_COOKIES: Optional[str] = Field(
        None,
        description="Ozon cookies",
        example="cookie1=value1; cookie2=value2"
    )
    CUSTUMER_COOKIES: Optional[str] = Field(
        None,
        description="Customer cookies",
        example="cookie1=value1; cookie2=value2"
    )
    STATUS:  Optional[bool] = Field(
        True,
        description="Работает ли набор ключей?",
        example=True
    )


class ApiKeyCreate(ApiKeyBase):
    pass

class ApiKeyUpdate(ApiKeyBase):
    pass

class ApiKeyResponse(ApiKeyBase):
    id: str = Field(
        ...,
        description="Unique identifier of the API key set",
        example="550e8400-e29b-41d4-a716-446655440000"
    )

    class Config:
        orm_mode = True  # Позволяет Pydantic работать с SQLAlchemy моделями
