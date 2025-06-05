# src/neural/neural_network.py
import random
import aiohttp
import logging
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, exists
from typing import Dict, Optional, Any, List
from datetime import datetime
from sqlalchemy.exc import SQLAlchemyError

from src.database import async_session
from src.models import Review, ProductInfo, NeuralResponse, LogsNeuro, PredefinedResponse
from src.utils.logger import get_logger
from src.neural.get_promt import get_prompt_for_sku

logger = get_logger(__name__)


class ReviewProcessor:
    def __init__(self, session_maker):
        self.session_maker = session_maker
        self.predefined_responses = []

    async def process_unprocessed_reviews(self, api_keys_dict: Dict[str, Any]) -> Dict[str, int]:
        """Основная функция обработки необработанных отзывов"""
        processed = errors = 0

        if not api_keys_dict.get('OZON_CLIENT_ID'):
            logger.error("Отсутствует OZON_CLIENT_ID в api_keys_dict")
            return {"processed": 0, "errors": 0}

        async with self.session_maker() as db:
            try:
                await self._load_predefined_responses(db)
                review_ids = await self._get_review_ids(db, api_keys_dict['OZON_CLIENT_ID'])

                if not review_ids:
                    return {"processed": 0, "errors": 0}

                reviews_data = await self._get_reviews_data(db, review_ids)

                for review, product_info in reviews_data:
                    try:
                        success = await self._process_single_review(
                            db=db,
                            review=review,
                            product_info=product_info,
                            api_key=api_keys_dict.get('YANDEX_GPT_API_KEY'),
                            folder=api_keys_dict.get('yandex_gpt_folder')
                        )
                        if success:
                            processed += 1
                        else:
                            errors += 1
                    except Exception as e:
                        await db.rollback()
                        logger.error(f"Ошибка обработки отзыва {review.id}: {e}")
                        errors += 1

                return {"processed": processed, "errors": errors}

            except Exception as e:
                await db.rollback()
                logger.error(f"Критическая ошибка: {e}")
                return {"processed": processed, "errors": errors + 1}

    async def get_gpt_response(
            self,
            review_text: str,
            api_keys_dict: Dict[str, Any],
            product_name: Optional[str] = None,
            sku: Optional[int] = None,
            rating: Optional[int] = None
    ) -> str:
        """Получение ответа от Yandex GPT"""
        if not api_keys_dict.get('YANDEX_GPT_API_KEY'):
            raise ValueError("Отсутствует Yandex GPT API ключ")
        if not api_keys_dict.get('yandex_gpt_folder'):
            raise ValueError("Отсутствует Yandex GPT FOLDER")

        async with self.session_maker() as db:
            try:
                system_prompt = await self._build_system_prompt(db, sku)
                context = self._build_context(product_name, rating)
                messages = self._prepare_messages(system_prompt, context, review_text)

                return await self._call_yagpt_api(
                    folder=api_keys_dict['yandex_gpt_folder'],
                    api_key=api_keys_dict['YANDEX_GPT_API_KEY'],
                    messages=messages
                )
            except Exception as e:
                logger.error(f"Ошибка GPT: {e}")
                return self._generate_fallback_response(product_name, rating)

    async def _load_predefined_responses(self, db: AsyncSession) -> None:
        """Загрузка шаблонных ответов из БД"""
        result = await db.execute(select(PredefinedResponse.text))
        self.predefined_responses = result.scalars().all()

    async def _get_review_ids(self, db: AsyncSession, client_id: str) -> List[int]:
        """Получение ID необработанных отзывов"""
        return (await db.execute(
            select(Review.id)
            .where(and_(
                Review.client_id == client_id,
                Review.status == "UNPROCESSED",
                ~exists().where(NeuralResponse.review_id == Review.id)
            ))
            .with_for_update(skip_locked=True)
            .limit(100)
        )).scalars().all()

    async def _get_reviews_data(self, db: AsyncSession, review_ids: List[int]) -> List[tuple]:
        """Получение данных отзывов и информации о товарах"""
        return (await db.execute(
            select(Review, ProductInfo)
            .join(ProductInfo, Review.id == ProductInfo.review_id, isouter=True)
            .where(Review.id.in_(review_ids))
        )).all()

    async def _process_single_review(
            self,
            db: AsyncSession,
            review: Review,
            product_info: Optional[ProductInfo],
            api_key: Optional[str],
            folder: Optional[str]
    ) -> bool:
        """Обработка одного отзыва"""
        if not api_key:
            raise ValueError("Отсутствует API ключ")

        try:
            response_text = await self.get_gpt_response(
                review_text=review.text or "",
                api_keys_dict={
                    'YANDEX_GPT_API_KEY': api_key,
                    'yandex_gpt_folder': folder
                },
                product_name=product_info.product_name if product_info else None,
                sku=review.sku,
                rating=review.rating
            )

            await self._save_response(
                db=db,
                review_id=review.id,
                review_text=review.text,
                response_text=response_text
            )
            return True
        except Exception as e:
            await self._log_error(
                db=db,
                review_text=review.text,
                error=str(e)
            )
            return False

    async def _build_system_prompt(self, db: AsyncSession, sku: Optional[int]) -> str:
        """Создание системного промпта для GPT"""
        try:
            prompt = await get_prompt_for_sku(db, sku)
            examples = "\n".join(
                f"- {resp}" for resp in random.sample(
                    self.predefined_responses,
                    min(3, len(self.predefined_responses))
                ))
            return f"{prompt or ''}\n\nПримеры ответов:\n{examples}, Вдохновляйся этими примерами и перефразируй их, не пиши спасибо или благ"
        except Exception as e:
            logger.error(f"Ошибка создания промпта: {e}")
            return "Спасибо за ваш отзыв! Мы ценим ваше мнение."

    def _build_context(self, product_name: Optional[str], rating: Optional[int]) -> str:
        """Формирование контекста для GPT"""
        context = []
        if product_name:
            context.append(f"Товар: {product_name}")
        if rating is not None:
            context.append(f"Оценка: {rating}/5")
        return "\n".join(context) if context else ""

    def _prepare_messages(self, system_prompt: str, context: str, review_text: str) -> List[Dict]:
        """Подготовка сообщений для GPT API"""
        return [
            {
                "role": "system",
                "text": f"{system_prompt}\n\n{context}" if context else system_prompt
            },
            {
                "role": "user",
                "text": review_text or "Пользователь не оставил комментарий"
            }
        ]

    async def _call_yagpt_api(self, api_key: str, folder: str, messages: List[Dict]) -> str:
        """Вызов API Yandex GPT"""
        payload = {
            "modelUri": f"gpt://{folder}/yandexgpt-lite",
            "completionOptions": {
                "stream": False,
                "temperature": 0.6,
                "maxTokens": 1000,
            },
            "messages": messages
        }

        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(
                        "https://llm.api.cloud.yandex.net/foundationModels/v1/completion",
                        headers={
                            "Content-Type": "application/json",
                            "Authorization": f"Api-Key {api_key}"
                        },
                        json=payload,
                        timeout=30
                ) as response:
                    if response.status != 200:
                        error_text = await response.text()
                        raise ValueError(f"Ошибка API {response.status}: {error_text}")

                    result = await response.json()
                    return result['result']['alternatives'][0]['message']['text']
        except Exception as e:
            logger.error(f"Ошибка вызова API: {e}")
            raise

    async def _save_response(
            self,
            db: AsyncSession,
            review_id: str,
            review_text: Optional[str],
            response_text: str
    ) -> None:
        """Сохранение ответа в БД"""
        now = datetime.now().isoformat()
        try:
            db.add(NeuralResponse(
                review_id=review_id,
                response_text=response_text,
                created_at=now
            ))
            db.add(LogsNeuro(
                review_text=(review_text or "")[:500],
                response_text=response_text[:500],
                status='SUCCESS',
                created_at=now
            ))
            await db.commit()
        except Exception as e:
            await db.rollback()
            raise

    async def _log_error(
            self,
            db: AsyncSession,
            review_text: Optional[str],
            error: str
    ) -> None:
        """Логирование ошибки в БД"""
        now = datetime.now().isoformat()
        try:
            db.add(LogsNeuro(
                review_text=(review_text or "")[:500],
                response_text=error[:500],
                status='ERROR',
                created_at=now
            ))
            await db.commit()
        except Exception as e:
            await db.rollback()
            logger.error(f"Ошибка записи лога ошибки: {e}")

    def _generate_fallback_response(self, product_name: Optional[str], rating: Optional[int]) -> str:
        """Генерация резервного ответа при ошибке"""
        base_response = "Спасибо за ваш отзыв!"
        if product_name:
            base_response += f" Мы учтем ваше мнение о товаре {product_name}."
        if rating is not None and rating < 4:
            base_response += " Приносим извинения за доставленные неудобства."
        return base_response
def create_review_processor(session_maker):
    """Создаёт и возвращает экземпляр ReviewProcessor"""
    return ReviewProcessor(session_maker)

# Альтернативный вариант для обратной совместимости
async def get_gpt_response(
        review_text: str,
        api_keys_dict: Dict[str, Any],
        product_name: Optional[str] = None,
        sku: Optional[int] = None,
        rating: Optional[int] = None,
        session_maker=async_session
):
    """Совместимая версия функции get_gpt_response"""
    processor = ReviewProcessor(session_maker)
    return await processor.get_gpt_response(
        review_text=review_text,
        api_keys_dict=api_keys_dict,
        product_name=product_name,
        sku=sku,
        rating=rating
    )

async def process_unprocessed_reviews(api_keys_dict: Dict[str, Any], session_maker=async_session):
    """Совместимая версия функции process_unprocessed_reviews"""
    processor = ReviewProcessor(session_maker)
    return await processor.process_unprocessed_reviews(api_keys_dict)