import asyncio

import aiohttp
import logging
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_
from typing import Dict, Any, Optional, AsyncContextManager
from datetime import datetime
import dateutil.parser
from contextlib import asynccontextmanager

from src.config import OZON_API_URLS
from src.database import async_session
from src.models import (
    Review, ProductPrompt, ProductInfo, Comment, Photo, Video, ApiKeys, LogsNeuro
)
from src.utils.logger import get_logger

logger = get_logger(__name__)


class KeyStatusManager:
    """Контекстный менеджер для безопасного управления статусом API ключа"""

    def __init__(self, db: AsyncSession, key_id: str):
        self.db = db
        self.key_id = key_id
        self.key_record = None

    async def __aenter__(self):
        self.key_record = (await self.db.execute(
            select(ApiKeys)
            .where(ApiKeys.id == self.key_id)
        )).scalar_one()

        if self.key_record.STATUS is False:
            logger.warning(f"Key {self.key_id} is already in STATUS=False state")
            # Можно добавить логику восстановления или пропуска

        self.key_record.STATUS = False
        await self.db.commit()
        logger.info(f"Set STATUS=False for key {self.key_id}")
        return self.key_record

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        try:
            if self.key_record:
                self.key_record.STATUS = True
                await self.db.commit()
                logger.info(f"Restored STATUS=True for key {self.key_id}")

            if exc_type is not None:
                logger.error(f"Error in KeyStatusManager for key {self.key_id}: {exc_val}", exc_info=True)
                # Дополнительная обработка ошибок при необходимости

        except Exception as e:
            logger.critical(f"Failed to restore key status for {self.key_id}: {e}", exc_info=True)
            # Пытаемся восстановить соединение или записать ошибку
            try:
                await self.db.rollback()
            except:
                pass


async def get_last_id(db: AsyncSession, api_key_id: str) -> str:
    result = await db.execute(
        select(ApiKeys.LAST_ID)
        .where(ApiKeys.id == api_key_id)
    )
    return result.scalar() or ""


async def save_last_id(db: AsyncSession, api_key_id: str, last_id: str) -> None:
    key_record = (await db.execute(
        select(ApiKeys)
        .where(ApiKeys.id == api_key_id)
    )).scalar_one()
    key_record.LAST_ID = last_id
    await db.commit()
    logger.debug(f"Updated last_id to {last_id} for key {api_key_id}")


async def make_ozon_request(url: str, payload: Dict[str, Any], api_keys_dict: Dict[str, str], max_retries: int = 3) -> \
Optional[Dict[str, Any]]:
    headers = {
        'Client-Id': api_keys_dict['OZON_CLIENT_ID'],
        'Api-Key': api_keys_dict['OZON_API_KEY'],
        'Content-Type': 'application/json'
    }

    for attempt in range(max_retries):
        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(url, headers=headers, json=payload, timeout=30) as response:
                    response.raise_for_status()
                    data = await response.json()
                    logger.debug(f"API request to {url} succeeded (attempt {attempt + 1})")
                    return data
        except asyncio.TimeoutError:
            if attempt == max_retries - 1:
                logger.error(f"API request to {url} timed out after {max_retries} attempts")
                return None
            await asyncio.sleep(1)
        except aiohttp.ClientError as e:
            if attempt == max_retries - 1:
                logger.error(f"API request to {url} failed after {max_retries} attempts: {str(e)}")
                return None
            await asyncio.sleep(1)
        except Exception as e:
            logger.error(f"Unexpected error in API request to {url}: {str(e)}")
            return None


async def parse_ozon_date(date_str: Optional[str]) -> datetime:
    if not date_str:
        return datetime.now()
    try:
        return dateutil.parser.isoparse(date_str)
    except ValueError:
        logger.warning(f"Failed to parse date: {date_str}")
        return datetime.now()


async def fetch_and_save_reviews(api_keys_dict: Dict[str, str]) -> None:
    async with async_session() as db:
        try:
            async with KeyStatusManager(db, api_keys_dict['id']) as key_record:
                last_id = await get_last_id(db, api_keys_dict['id'])
                payload = {
                    "status": "ALL",
                    "last_id": last_id,
                    "limit": 50,
                    "sort_dir": "ASC"
                }

                data = await make_ozon_request(OZON_API_URLS['review_list'], payload, api_keys_dict)
                if not data or not data.get('reviews'):
                    logger.info(f"No new reviews for client {api_keys_dict['OZON_CLIENT_ID']}")
                    return

                for review in data['reviews']:
                    try:
                        details = await make_ozon_request(
                            OZON_API_URLS['review_info'],
                            {"review_id": review['id']},
                            api_keys_dict
                        ) or {}

                        published_at = await parse_ozon_date(review.get('published_at'))

                        product_info = await make_ozon_request(
                            OZON_API_URLS['product_info'],
                            {"sku": [str(review['sku'])]},
                            api_keys_dict
                        ) or {}

                        await save_review_data(db, {
                            **review,
                            'published_at': published_at,
                            'product_name': product_info.get('items', [{}])[0].get('name', ''),
                            'comments': [{
                                **c,
                                'published_at': await parse_ozon_date(c.get('published_at'))
                            } for c in details.get('comments', [])],
                            'photos': details.get('photos', []),
                            'videos': details.get('videos', [])
                        }, api_keys_dict)

                    except Exception as e:
                        logger.error(f"Error processing review {review['id']}: {e}", exc_info=True)
                        continue

                if data.get('last_id'):
                    await save_last_id(db, api_keys_dict['id'], data['last_id'])

        except Exception as e:
            logger.error(f"Critical error in fetch_and_save_reviews for key {api_keys_dict['id']}: {e}", exc_info=True)
            raise


async def save_review_data(db: AsyncSession, review_data: Dict[str, Any], api_keys_dict: Dict[str, str]) -> None:
    try:
        existing_review = await db.execute(
            select(Review)
            .where(Review.id == review_data['id'])
            .where(Review.client_id == api_keys_dict['OZON_CLIENT_ID'])
        )

        if not existing_review.scalar_one_or_none():
            db.add(Review(
                id=review_data['id'],
                sku=review_data['sku'],
                text=review_data['text'],
                rating=review_data['rating'],
                status=review_data['status'],
                published_at=review_data['published_at'],
                client_id=api_keys_dict['OZON_CLIENT_ID']
            ))

            db.add(ProductInfo(
                review_id=review_data['id'],
                sku=review_data['sku'],
                product_name=review_data.get('product_name', '')
            ))

            existing_prompt = await db.execute(
                select(ProductPrompt)
                .where(ProductPrompt.sku == review_data['sku'])
            )

            if not existing_prompt.scalar_one_or_none():
                db.add(ProductPrompt(sku=review_data['sku']))

            await save_comments_and_media(db, review_data)

        await db.commit()
    except Exception as e:
        await db.rollback()
        logger.error(f"Failed to save review data: {e}", exc_info=True)
        raise


async def save_comments_and_media(db: AsyncSession, review_data: Dict[str, Any]) -> None:
    try:
        for comment in review_data.get('comments', []):
            existing_comment = await db.execute(
                select(Comment)
                .where(Comment.id == comment['id'])
            )

            if not existing_comment.scalar_one_or_none():
                db.add(Comment(
                    id=comment['id'],
                    review_id=review_data['id'],
                    text=comment.get('text', ''),
                    published_at=comment.get('published_at')
                ))

        for media_type, model in [('photos', Photo), ('videos', Video)]:
            for item in review_data.get(media_type, []):
                db.add(model(
                    review_id=review_data['id'],
                    url=item['url'],
                    **{k: v for k, v in item.items() if k != 'url' and hasattr(model, k)}
                ))
    except Exception as e:
        logger.error(f"Error saving comments/media: {e}")
        raise