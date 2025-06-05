# src/parcer/scheduler.py
import asyncio
import logging
from datetime import datetime
from typing import List, Dict, Any

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, insert

from src.database import async_session
from src.models import ApiKeys, Log
from src.config import SCHEDULE_INTERVAL
from src.parcer.fetch_reviews import fetch_and_save_reviews
from src.parcer.fetch_from_json import fetch_from_json
from src.neural.neural_network import ReviewProcessor
from src.utils.logger import get_logger
from src.parcer.consumer_module import OzonConsumer
from src.rabbitmq_scripts.auto_send import send_filtered_reviews

logger = get_logger(__name__)


class AsyncScheduler:
    def __init__(self, session_maker):
        self.active_tasks = set()
        self.session_maker = session_maker
        self.consumer = OzonConsumer()
        self._running = False
        self._fetch_json_counter = {}
        # Инициализируем процессор отзывов с фабрикой сессий
        self.review_processor = ReviewProcessor(session_maker)

    async def log_to_db(self, status: str, message: str):
        """Запись логов в базу данных"""
        try:
            async with self.session_maker() as session:
                try:
                    await session.execute(
                        insert(Log).values(
                            timestamp=datetime.now().isoformat(),
                            status=status,
                            message=message
                        )
                    )
                    await session.commit()
                except Exception as e:
                    logger.error(f"Ошибка записи лога: {str(e)}")
                    await session.rollback()
        except Exception as e:
            logger.error(f"Ошибка подключения к БД: {str(e)}")

    async def _safe_wrapper(self, coro, task_name=""):
        """Безопасная обёртка для корутин"""
        try:
            return await coro
        except Exception as e:
            error_msg = f"Ошибка в задаче {task_name}: {str(e)}"
            logger.error(error_msg, exc_info=True)
            await self.log_to_db(status="error", message=error_msg)
            return None

    async def get_api_keys(self):
        """Получение всех API ключей из БД"""
        async with self.session_maker() as session:
            try:
                result = await session.execute(select(ApiKeys))
                return result.scalars().all()
            except Exception as e:
                logger.error(f"Ошибка получения ключей: {str(e)}")
                await self.log_to_db(
                    status="error",
                    message=f"Ошибка получения ключей: {str(e)}"
                )
                return []

    async def process_key(self, key):
        """Обработка одного API ключа"""
        key_data = {
            'id': key.id,
            'yandex_gpt_folder': key.yandex_gpt_folder,
            'YANDEX_GPT_API_KEY': key.YANDEX_GPT_API_KEY,
            'OZON_API_KEY': key.OZON_API_KEY,
            'OZON_CLIENT_ID': key.OZON_CLIENT_ID,
            'LAST_ID': key.LAST_ID,
            'TIMESTUMP': key.TIMESTUMP,
            'IS_PREMIUM_PLUS': key.IS_PREMIUM_PLUS,
            'OZON_COOKIES': key.OZON_COOKIES,
            'CUSTUMER_COOKIES': key.CUSTUMER_COOKIES,
            'STATUS': key.STATUS
        }

        if key.IS_PREMIUM_PLUS:
            await self._safe_wrapper(
                fetch_and_save_reviews(key_data),
                f"fetch_and_save_reviews_for_key_{key.id}"
            )
        else:
            async with self.session_maker() as session:
                for i in range(5):
                    logger.info(f"Запуск fetch_from_json для ключа {key.id}, попытка {i + 1}/5")
                    await self._safe_wrapper(
                        fetch_from_json(key_data, session),
                        f"fetch_from_json_for_key_{key.id}_attempt_{i + 1}"
                    )
                    await asyncio.sleep(1)

    async def run_fetch_tasks(self):
        """Запуск задач получения отзывов"""
        keys = await self.get_api_keys()
        if not keys:
            logger.warning("Не найдено API ключей для обработки")
            return

        tasks = [self.process_key(key) for key in keys]
        await asyncio.gather(*tasks)

    async def run_processing_task(self):
        """Запуск обработки отзывов"""
        keys = await self.get_api_keys()
        if not keys:
            logger.warning("Не найдено API ключей для обработки")
            return

        tasks = []
        for key in keys:
            task = self._safe_wrapper(
                self.review_processor.process_unprocessed_reviews({
                    'id': key.id,
                    'yandex_gpt_folder': key.yandex_gpt_folder,
                    'YANDEX_GPT_API_KEY': key.YANDEX_GPT_API_KEY,
                    'OZON_API_KEY': key.OZON_API_KEY,
                    'OZON_CLIENT_ID': key.OZON_CLIENT_ID,
                    'LAST_ID': key.LAST_ID,
                    'TIMESTUMP': key.TIMESTUMP,
                    'IS_PREMIUM_PLUS': key.IS_PREMIUM_PLUS,
                    'OZON_COOKIES': key.OZON_COOKIES,
                    'CUSTUMER_COOKIES': key.CUSTUMER_COOKIES,
                    'STATUS': key.STATUS
                }),
                f"process_reviews_for_key_{key.id}"
            )
            tasks.append(task)

        await asyncio.gather(*tasks)

    async def run_queue_sending(self):
        """Отправка отзывов в очередь"""
        async with self.session_maker() as session:
            try:
                result = await send_filtered_reviews(session)
                await session.commit()
                return result
            except Exception as e:
                await session.rollback()
                logger.error(f"Ошибка отправки в очередь: {str(e)}", exc_info=True)
                return 0

    async def main_loop(self):
        """Основной цикл работы планировщика"""
        self._running = True
        logger.info("Запуск планировщика")
        last_consumer_refresh = datetime.now()

        try:
            # Инициализация consumer
            if hasattr(self.consumer, 'start'):
                start_result = self.consumer.start()
                if asyncio.iscoroutine(start_result):
                    await self._safe_wrapper(start_result, "consumer_start")
                else:
                    logger.warning("consumer.start() не является корутиной, пропускаем await")

            while self._running:
                try:
                    # Проверяем, нужно ли обновить consumer (каждые 30 минут)
                    current_time = datetime.now()
                    if (current_time - last_consumer_refresh).total_seconds() >= 1800:  # 1800 секунд = 30 минут
                        logger.info("Обновление подключения consumer...")

                        # Сначала останавливаем старый consumer
                        if hasattr(self.consumer, 'stop'):
                            try:
                                stop_result = self.consumer.stop()
                                if asyncio.iscoroutine(stop_result):
                                    await stop_result
                            except Exception as e:
                                logger.error(f"Ошибка остановки consumer: {str(e)}")

                        # Затем создаем новый экземпляр и запускаем его
                        self.consumer = OzonConsumer()
                        if hasattr(self.consumer, 'start'):
                            start_result = self.consumer.start()
                            if asyncio.iscoroutine(start_result):
                                await self._safe_wrapper(start_result, "consumer_restart")

                        last_consumer_refresh = current_time
                        logger.info("Подключение consumer успешно обновлено")

                    # Основной цикл обработки
                    await self.run_processing_task()
                    await asyncio.sleep(5)

                    # Дополнительные задачи
                    await self.run_fetch_tasks()
                    await asyncio.sleep(60)
                    # await self.run_queue_sending()
                    # await asyncio.sleep(30)

                except asyncio.CancelledError:
                    break
                except Exception as e:
                    logger.error(f"Ошибка в основном цикле: {str(e)}", exc_info=True)
                    await asyncio.sleep(10)

        except Exception as e:
            logger.critical(f"Критическая ошибка: {str(e)}", exc_info=True)
        finally:
            await self.shutdown()

    async def shutdown(self):
        """Корректное завершение работы"""
        self._running = False
        logger.info("Остановка планировщика...")

        # Отмена всех активных задач
        for task in self.active_tasks:
            if not task.done():
                task.cancel()
                try:
                    await task
                except Exception:
                    pass

        # Остановка consumer
        if hasattr(self.consumer, 'stop'):
            try:
                stop_result = self.consumer.stop()
                if asyncio.iscoroutine(stop_result):
                    await stop_result
            except Exception as e:
                logger.error(f"Ошибка остановки consumer: {str(e)}")

        # Фиксация завершения работы
        try:
            await self.log_to_db(
                status="info",
                message="Планировщик корректно остановлен"
            )
        except Exception as e:
            logger.error(f"Ошибка записи лога завершения: {str(e)}")


async def main():
    scheduler = AsyncScheduler(async_session)
    try:
        await scheduler.main_loop()
    except KeyboardInterrupt:
        logger.info("Планировщик остановлен пользователем")
        await scheduler.log_to_db(
            status="info",
            message="Планировщик остановлен пользователем"
        )
    except Exception as e:
        logger.error(f"Аварийное завершение: {e}")
        await scheduler.log_to_db(
            status="error",
            message=f"Аварийное завершение: {str(e)}"
        )
    finally:
        await scheduler.shutdown()


if __name__ == "__main__":
    asyncio.run(main())