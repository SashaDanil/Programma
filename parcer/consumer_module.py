import os
import json
import pika
from typing import Dict, Any
from pika.adapters.blocking_connection import BlockingChannel
from sqlalchemy.orm import Session
from sqlalchemy import select
from src.config import headers
from src.database import get_db
from src.models import Review, ApiKeys
from src.api.logger import logger
from datetime import datetime
from pathlib import Path
import requests
import threading
import time


class OzonConsumer:
    def __init__(self):
        self._connection = None
        self._channel = None
        self._running = False
        self._thread = None

        # Конфигурация RabbitMQ
        self.RABBITMQ_HOST = os.environ.get('RABBITMQ_HOST', '147.45.151.180')
        self.RABBITMQ_PORT = int(os.environ.get('RABBITMQ_PORT', '5672'))
        self.RABBITMQ_USERNAME = os.environ.get('RABBITMQ_USERNAME', 'admin')
        self.RABBITMQ_PASSWORD = os.environ.get('RABBITMQ_PASSWORD', 'Valera_228')
        self.QUEUE_NAME = 'reviews_ozon'
        
        # Другие настройки
        self.RESPONSES_FILE = 'server_responses.txt'
        self.OZON_API_URL = "https://api-seller.ozon.ru/v1/review/comment/create"
        self.OZON_DIRECT_URL = "https://seller.ozon.ru/api/review/comment/create"
        self.MAX_ATTEMPTS = 5
        self.RETRY_DELAY = 5  # seconds

        # Базовые заголовки для Ozon API
        self.OZON_HEADERS = {
            "Content-Type": "application/json"
        }

        # Создаем директорию для логов
        Path("logs").mkdir(exist_ok=True)

    def save_server_response(self, response_data: Dict[str, Any], client_id: str, review_id: str):
        """Сохраняет ответ сервера в текстовый файл"""
        try:
            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            log_entry = {
                "timestamp": timestamp,
                "client_id": client_id,
                "review_id": review_id,
                "response": response_data
            }

            with open(f"logs/{self.RESPONSES_FILE}", "a", encoding="utf-8") as f:
                f.write(json.dumps(log_entry, ensure_ascii=False) + "\n")

        except Exception as e:
            logger.error(f"Ошибка при записи ответа сервера: {str(e)}")

    def check_premium_plus(self, db: Session, client_id: str) -> bool:
        """Проверяет, есть ли у клиента подписка Premium Plus"""
        api_key = db.query(ApiKeys).filter(ApiKeys.OZON_CLIENT_ID == client_id).first()
        return bool(api_key and api_key.IS_PREMIUM_PLUS)

    def get_client_cookies_and_headers(self, db: Session, client_id: str) -> tuple:
        """Получает cookies и headers для конкретного клиента"""
        api_key_record = db.query(ApiKeys).filter(ApiKeys.OZON_CLIENT_ID == client_id).first()

        if not api_key_record:
            logger.error(f"No API keys found for client {client_id}")
            raise ValueError(f"No API keys found for client {client_id}")

        if not api_key_record.CUSTUMER_COOKIES:
            logger.error(f"No cookies found for client {client_id}")
            raise ValueError(f"No cookies found for client {client_id}")

        cookies = {}
        for cookie_item in api_key_record.CUSTUMER_COOKIES.split(';'):
            key_value = cookie_item.strip().split('=', 1)
            if len(key_value) == 2:
                key, value = key_value
                cookies[key] = value

        cookies['sc_company_id'] = str(client_id)

        headers['x-o3-company-id'] = str(client_id)

        return cookies, headers

    def send_to_ozon_direct(self, review_uuid: str, text: str, client_id: str) -> Dict[str, Any]:
        """Отправляет ответ на отзыв напрямую через веб-интерфейс Ozon и проверяет статус обработки"""
        db = next(get_db())
        try:
            cookies, headers = self.get_client_cookies_and_headers(db, client_id)
            api_key = db.query(ApiKeys).filter(ApiKeys.OZON_CLIENT_ID == client_id).first()
            if not api_key:
                raise ValueError(f"API ключи для client_id {client_id} не найдены")

            # Первый запрос - отправка ответа на отзыв
            json_data = {
                'text': text,
                'review_uuid': review_uuid,
                'company_type': 'seller',
                'company_id': client_id
            }

            response = requests.post(
                self.OZON_DIRECT_URL,
                cookies=cookies,
                headers=headers,
                json=json_data,
                timeout=10
            )
            response.raise_for_status()
            response_data = response.json()
            for attempt in range(1, self.MAX_ATTEMPTS + 1):
                try:
                    if response_data.get('result', False):
                        # Если ответ успешен, делаем второй запрос для проверки статуса
                        status_check_data = {
                            'company_id': client_id,
                            'company_type': 'seller',
                            'review_uuid': review_uuid,
                        }

                        status_response = requests.post(
                            'https://seller.ozon.ru/api/v2/review/detail',
                            cookies=cookies,
                            headers=headers,
                            json=status_check_data,
                            timeout=10
                        )
                        status_response.raise_for_status()
                        status_data = status_response.json()

                        # Проверяем статус обработки
                        interaction_status = status_data.get('interaction_status', '').lower()
                        if interaction_status in ('processed', 'process'):
                            self.save_server_response(response_data, client_id, review_uuid)
                            return response_data
                        else:
                            # Если статус не PROCESSED, считаем это ошибкой и повторяем
                            raise ValueError(f"Неверный статус обработки отзыва: {interaction_status}")

                    if attempt < self.MAX_ATTEMPTS:
                        logger.warning(
                            f"Попытка {attempt} из {self.MAX_ATTEMPTS}: Ошибка в ответе Ozon Direct. Повтор через {self.RETRY_DELAY} сек...")
                        time.sleep(self.RETRY_DELAY)
                        continue

                    raise ValueError(f"Неверный ответ от Ozon Direct после {self.MAX_ATTEMPTS} попыток")

                except Exception as e:
                    if attempt == self.MAX_ATTEMPTS:
                        raise
                    logger.warning(
                        f"Попытка {attempt} из {self.MAX_ATTEMPTS}: Ошибка при отправке в Ozon Direct. Повтор через {self.RETRY_DELAY} сек...")
                    time.sleep(self.RETRY_DELAY)

        except Exception as e:
            error_msg = f"Direct API error: {str(e)}"
            logger.error(error_msg)
            error_response = {"error": error_msg}
            self.save_server_response(error_response, client_id, review_uuid)
            return error_response
        finally:
            db.close()

    def send_to_ozon_api(self, review_id: str, response_text: str, client_id: str) -> Dict[str, Any]:
        """Отправляет ответ на отзыв через Ozon API (для Premium Plus)"""
        db = next(get_db())
        try:
            for attempt in range(1, self.MAX_ATTEMPTS + 1):
                try:
                    api_key = db.query(ApiKeys).filter(ApiKeys.OZON_CLIENT_ID == client_id).first()
                    if not api_key or not api_key.OZON_API_KEY:
                        raise ValueError(f"API ключи для client_id {client_id} не найдены")

                    headers = self.OZON_HEADERS.copy()
                    headers["Client-Id"] = client_id
                    headers["Api-Key"] = api_key.OZON_API_KEY

                    payload = {
                        "mark_review_as_processed": True,
                        "parent_comment_id": None,
                        "review_id": review_id,
                        "text": response_text
                    }

                    response = requests.post(
                        self.OZON_API_URL,
                        headers=headers,
                        json=payload,
                        timeout=10
                    )
                    response.raise_for_status()
                    response_data = response.json()

                    if 'comment_id' in response_data:
                        self.save_server_response(response_data, client_id, review_id)
                        return response_data

                    if attempt < self.MAX_ATTEMPTS:
                        logger.warning(
                            f"Попытка {attempt} из {self.MAX_ATTEMPTS}: Ошибка в ответе Ozon API. Повтор через {self.RETRY_DELAY} сек...")
                        time.sleep(self.RETRY_DELAY)
                        continue

                    raise ValueError(f"Неверный ответ от Ozon API после {self.MAX_ATTEMPTS} попыток")

                except Exception as e:
                    if attempt == self.MAX_ATTEMPTS:
                        raise
                    logger.warning(
                        f"Попытка {attempt} из {self.MAX_ATTEMPTS}: Ошибка при отправке в Ozon API. Повтор через {self.RETRY_DELAY} сек...")
                    time.sleep(self.RETRY_DELAY)

        except Exception as e:
            error_msg = f"Ozon API error: {str(e)}"
            logger.error(error_msg)
            error_response = {"error": error_msg}
            self.save_server_response(error_response, client_id, review_id)
            return error_response
        finally:
            db.close()

    def update_review_status(self, db: Session, review_id: str, status: str):
        """Обновляет статус отзыва"""
        try:
            db.query(Review).filter(Review.id == review_id).update(
                {"status": status},
                synchronize_session=False
            )
            db.commit()
            logger.info(f"Статус отзыва {review_id} изменен на {status}")
        except Exception as e:
            db.rollback()
            logger.error(f"Ошибка обновления статуса: {str(e)}")
            raise

    def process_message(self, ch: BlockingChannel, method, properties, body):
        """Обрабатывает сообщение из очереди"""
        db = None
        try:
            message = json.loads(body)
            review_id = message.get("review_id")
            response_text = message.get("response_text")
            client_id = message.get("client_id")

            if not all([review_id, response_text, client_id]):
                raise ValueError("Не хватает review_id, response_text или client_id в сообщении")

            db = next(get_db())
            is_premium_plus = self.check_premium_plus(db, client_id)

            if is_premium_plus:
                api_response = self.send_to_ozon_api(review_id, response_text, client_id)
                success = 'comment_id' in api_response
            else:
                api_response = self.send_to_ozon_direct(review_id, response_text, client_id)
                success = api_response.get('result', False)

            if success:
                self.update_review_status(db, review_id, "PROCESSED")
                ch.basic_ack(delivery_tag=method.delivery_tag)
                logger.info(f"Успешно обработан отзыв {review_id}")
            else:
                self.update_review_status(db, review_id, "InQueueError")
                ch.basic_nack(delivery_tag=method.delivery_tag, requeue=False)
                logger.error(f"Ошибка обработки отзыва {review_id}. Ответ API: {api_response}")

        except json.JSONDecodeError as e:
            logger.error(f"Невалидный JSON в сообщении: {str(e)}")
            if db and 'review_id' in locals():
                self.update_review_status(db, review_id, "InQueueError")
            ch.basic_nack(delivery_tag=method.delivery_tag, requeue=False)
        except Exception as e:
            logger.error(f"Ошибка обработки сообщения: {str(e)}")
            if db and 'review_id' in locals():
                self.update_review_status(db, review_id, "InQueueError")
            ch.basic_nack(delivery_tag=method.delivery_tag, requeue=False)
        finally:
            if db:
                db.close()

    def _run_consumer(self):
        """Основной цикл consumer'а"""
        try:
            self._connection = pika.BlockingConnection(
                pika.ConnectionParameters(host=self.RABBITMQ_HOST, port=self.RABBITMQ_PORT,
                                         credentials=pika.PlainCredentials(self.RABBITMQ_USERNAME, self.RABBITMQ_PASSWORD))
            )
            self._channel = self._connection.channel()
            self._channel.queue_declare(queue=self.QUEUE_NAME, durable=True)
            self._channel.basic_qos(prefetch_count=1)

            self._channel.basic_consume(
                queue=self.QUEUE_NAME,
                on_message_callback=self.process_message,
                auto_ack=False
            )

            logger.info(f"Consumer запущен для очереди {self.QUEUE_NAME}")
            while self._running:
                self._connection.process_data_events(time_limit=1)

        except Exception as e:
            logger.error(f"Ошибка в consumer: {str(e)}")
        finally:
            if self._connection and self._connection.is_open:
                self._connection.close()

    def start(self):
        """Запускает consumer в отдельном потоке"""
        if self._running:
            logger.warning("Consumer уже запущен")
            return

        self._running = True
        self._thread = threading.Thread(target=self._run_consumer, daemon=True)
        self._thread.start()
        logger.info("Consumer запущен в фоновом режиме")

    def stop(self):
        """Останавливает consumer"""
        if not self._running:
            return

        self._running = False
        if self._thread:
            self._thread.join(timeout=5)
        logger.info("Consumer остановлен")