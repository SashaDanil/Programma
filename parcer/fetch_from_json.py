from datetime import datetime
from typing import Dict, Any, Optional
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
import aiohttp
import asyncio
from src.models import Review, ProductPrompt, ProductInfo, Photo, Video, ApiKeys
from src.utils.logger import get_logger
from src.config import headers
import dateutil.parser
from contextlib import asynccontextmanager

logger = get_logger(__name__)


class KeyStatusManager:
    """Контекстный менеджер для безопасного управления статусом API ключа"""

    def __init__(self, db: AsyncSession, key_id: str):
        self.db = db
        self.key_id = key_id
        self.key_obj = None
        self.should_restore = True  # Флаг, определяющий нужно ли восстанавливать статус

    async def __aenter__(self):
        self.key_obj = (await self.db.execute(
            select(ApiKeys)
            .where(ApiKeys.OZON_CLIENT_ID == self.key_id)
        )).scalar_one_or_none()

        if not self.key_obj:
            raise ValueError(f"No API keys found for client {self.key_id}")

        if not self.key_obj.STATUS:
            logger.warning(f"Key {self.key_id} is already in STATUS=False state")

        self.key_obj.STATUS = False
        await self.db.commit()
        logger.info(f"Set STATUS=False for key {self.key_id}")
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        try:
            if self.key_obj and self.should_restore:
                self.key_obj.STATUS = True
                await self.db.commit()
                logger.info(f"Restored STATUS=True for key {self.key_id}")

            if exc_type is not None:
                logger.error(f"Error in KeyStatusManager for key {self.key_id}: {exc_val}", exc_info=True)

        except Exception as e:
            logger.critical(f"Failed to restore key status for {self.key_id}: {e}", exc_info=True)
            try:
                await self.db.rollback()
            except:
                pass


async def get_pagination_data(db: AsyncSession, seller_id: str) -> Dict[str, str]:
    result = await db.execute(
        select(ApiKeys.LAST_ID, ApiKeys.TIMESTUMP)
        .where(ApiKeys.OZON_CLIENT_ID == seller_id)
    )
    row = result.first()
    return {'last_id': row[0] or "", 'timestump': row[1] or ""} if row else {'last_id': "", 'timestump': ""}


async def save_pagination_data(db: AsyncSession, seller_id: str, last_id: str, timestump: str) -> None:
    key_record = (await db.execute(
        select(ApiKeys)
        .where(ApiKeys.OZON_CLIENT_ID == seller_id)
    )).scalar_one()

    if last_id:
        key_record.LAST_ID = last_id
    if timestump:
        key_record.TIMESTUMP = timestump

    await db.commit()
    logger.debug(f"Updated pagination data for client {seller_id}")


async def make_ozon_seller_request(url: str, payload: Dict[str, Any], cookies: Dict[str, str], max_retries: int = 3) -> \
Optional[Dict[str, Any]]:
    for attempt in range(max_retries):
        try:
            async with aiohttp.ClientSession(cookies=cookies, headers=headers) as session:
                async with session.post(url, json=payload, timeout=30) as response:
                    if response.status != 200:
                        error_data = await response.json()
                        logger.error(
                            f"API request failed with status {response.status}: {error_data.get('message', 'Unknown error')}")
                        return {'error': error_data}

                    data = await response.json()
                    logger.debug(f"API request to {url} succeeded (attempt {attempt + 1})")
                    return data
        except asyncio.TimeoutError:
            if attempt == max_retries - 1:
                logger.error(f"API request to {url} timed out after {max_retries} attempts")
                return {'error': {'message': 'Request timeout'}}
            await asyncio.sleep(1)
        except aiohttp.ClientError as e:
            if attempt == max_retries - 1:
                logger.error(f"API request to {url} failed after {max_retries} attempts: {str(e)}")
                return {'error': {'message': str(e)}}
            await asyncio.sleep(1)
        except Exception as e:
            logger.error(f"Unexpected error in API request to {url}: {str(e)}")
            return {'error': {'message': str(e)}}


async def parse_review_text(review_data: Dict[str, Any]) -> str:
    text_parts = []
    if review_data.get('advantages'):
        text_parts.append(f"Достоинства: {review_data['advantages']}")
    if review_data.get('disadvantages'):
        text_parts.append(f"Недостатки: {review_data['disadvantages']}")
    if review_data.get('comment'):
        text_parts.append(f"Комментарий: {review_data['comment']}")
    return "\n".join(text_parts) if text_parts else ""


async def parse_ozon_date(date_str: Optional[str]) -> datetime:
    if not date_str:
        return datetime.now()
    try:
        return dateutil.parser.isoparse(date_str)
    except ValueError:
        logger.warning(f"Failed to parse date: {date_str}")
        return datetime.now()


async def save_review_data(db: AsyncSession, review_data: Dict[str, Any], seller_id: str) -> bool:
    try:
        existing_review = await db.execute(
            select(Review)
            .where(Review.id == review_data['uuid'])
            .where(Review.client_id == seller_id)
        )

        if existing_review.scalar_one_or_none():
            return False

        review_text = await parse_review_text(review_data.get('text', {}))
        published_at = await parse_ozon_date(review_data.get('published_at'))

        status = "PROCESSED" if review_data.get('interaction_status') == "PROCESSED" else "UNPROCESSED"

        db.add(Review(
            id=review_data['uuid'],
            sku=int(review_data['sku']),
            text=review_text,
            rating=review_data['rating'],
            status=status,
            published_at=published_at,
            client_id=seller_id,
        ))

        db.add(ProductInfo(
            review_id=review_data['uuid'],
            sku=int(review_data['sku']),
            product_name=review_data['product']['title']
        ))

        existing_prompt = await db.execute(
            select(ProductPrompt)
            .where(ProductPrompt.sku == int(review_data['sku']))
        )
        if not existing_prompt.scalar_one_or_none():
            db.add(ProductPrompt(sku=int(review_data['sku'])))

        for media_type, model in [('photo', Photo), ('video', Video)]:
            for item in review_data.get(media_type, []):
                db.add(model(
                    review_id=review_data['uuid'],
                    url=item['url'],
                    **{k: v for k, v in item.items()
                       if k != 'url' and hasattr(model, k)}
                ))

        return True

    except Exception as e:
        logger.error(f"Error saving review data: {e}", exc_info=True)
        await db.rollback()
        return False


async def fetch_from_json(api_keys_dict: Dict[str, str], db: AsyncSession) -> Dict[str, Any]:
    """
    Получение отзывов через веб-интерфейс Ozon Seller
    :param api_keys_dict: Словарь с ключами API
    :param db: Асинхронная сессия SQLAlchemy
    :return: Словарь с результатами обработки
    """
    seller_id = api_keys_dict['OZON_CLIENT_ID']
    pagination_data = await get_pagination_data(db, seller_id)
    last_id = pagination_data['last_id']
    timestump = pagination_data['timestump']

    try:
        async with KeyStatusManager(db, seller_id) as key_manager:
            key = key_manager.key_obj

            if not key.OZON_COOKIES:
                logger.error(f"No cookies found for client {seller_id}")
                key.STATUS = False
                key_manager.should_restore = False  # Отключаем восстановление статуса
                await db.commit()
                return {'processed_count': 0, 'last_id': last_id, 'timestump': timestump}

            cookies_dict = {}
            for cookie_item in key.OZON_COOKIES.split(';'):
                key_value = cookie_item.strip().split('=', 1)
                if len(key_value) == 2:
                    key_name, value = key_value
                    cookies_dict[key_name] = value

            cookies_dict['sc_company_id'] = seller_id
            headers['x-o3-company-id'] = seller_id

            url = 'https://seller.ozon.ru/api/v3/review/list'
            payload = {
                'with_counters': False,
                'sort': {
                    'sort_by': 'PUBLISHED_AT',
                    'sort_direction': 'ASC',
                },
                'company_type': 'seller',
                'filter': {
                    'interaction_status': ['ALL'],
                },
                'company_id': int(seller_id),
            }

            if last_id:
                payload['pagination_last_uuid'] = last_id
            if timestump:
                payload['pagination_last_timestamp'] = timestump

            response = await make_ozon_seller_request(url, payload, cookies_dict)

            if response is None or 'error' in response:
                error_msg = response.get('error', {}).get('message', 'Unknown error') if response else 'No response'
                logger.error(f"API request failed for client {seller_id}: {error_msg}")

                if response and response.get('error', {}).get('code') in ['unauthorized', 'forbidden']:
                    key.STATUS = False
                    key_manager.should_restore = False  # Отключаем восстановление статуса
                    await db.commit()
                    logger.warning(f"Disabled key {seller_id} due to auth error")

                return {'processed_count': 0, 'last_id': last_id, 'timestump': timestump}

            if not response.get('result'):
                logger.info(f"No new reviews for client {seller_id}")
                return {'processed_count': 0, 'last_id': last_id, 'timestump': timestump}

            processed_count = 0
            new_last_id = response.get('pagination_last_uuid', last_id)
            new_timestump = response.get('pagination_last_timestamp', timestump)

            for review in response['result']:
                if await save_review_data(db, review, seller_id):
                    processed_count += 1

            if (new_last_id and new_last_id != last_id) or (new_timestump and new_timestump != timestump):
                await save_pagination_data(db, seller_id, new_last_id, new_timestump)

            return {
                'processed_count': processed_count,
                'last_id': new_last_id,
                'timestump': new_timestump
            }

    except Exception as e:
        logger.error(f"Error in fetch_from_json: {e}", exc_info=True)
        return {'processed_count': 0, 'last_id': last_id, 'timestump': timestump}