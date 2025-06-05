from typing import Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from src.models import Prompt, ProductPrompt
from src.utils.logger import get_logger

# Инициализация логгера
logger = get_logger(__name__)


async def get_prompt_for_sku(db: AsyncSession, sku: Optional[int]) -> str:
    """
    Получает промпт для конкретного SKU.

    Если для SKU есть кастомный промпт, добавляет его к активному промпту.
    Если активного промпта нет, используется дефолтный.

    Args:
        db: Асинхронная сессия базы данных
        sku: Артикул товара (опционально)

    Returns:
        str: Составной промпт для генерации ответа
    """
    logger.debug(f"Получение промпта для SKU: {sku}")

    # Получаем активный промпт (основной)
    result = await db.execute(select(Prompt.content).filter(Prompt.is_active == True))
    active_prompt = result.scalar_one_or_none()

    # Извлекаем текст промпта или используем дефолтный
    base_prompt = active_prompt if active_prompt else "отвечай на все: я робат бип боп бап"

    # Если передан SKU, пытаемся найти кастомный промпт
    if sku is not None:
        result = await db.execute(select(ProductPrompt.prompt).filter(ProductPrompt.sku == sku))
        custom_prompt = result.scalar_one_or_none()

        if custom_prompt:
            # Объединяем оба промпта через перенос строки
            final_prompt = f"{base_prompt}\n\n{custom_prompt}"
            logger.debug(f"Найден кастомный промпт для SKU {sku}")
            return final_prompt

    logger.debug("Используется только базовый промпт")
    return base_prompt
