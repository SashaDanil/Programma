import json
import os
from src.api.logger import logger
import pika


def send_to_rabbitmq(message: dict):
    try:
        # Настройки подключения к RabbitMQ
        RABBITMQ_HOST = os.environ.get('RABBITMQ_HOST', '147.45.151.180')
        RABBITMQ_PORT = int(os.environ.get('RABBITMQ_PORT', '5672'))
        RABBITMQ_USERNAME = os.environ.get('RABBITMQ_USERNAME', 'admin')
        RABBITMQ_PASSWORD = os.environ.get('RABBITMQ_PASSWORD', 'Valera_228')
        
        # Настройка параметров подключения
        credentials = pika.PlainCredentials(RABBITMQ_USERNAME, RABBITMQ_PASSWORD)
        parameters = pika.ConnectionParameters(
            host=RABBITMQ_HOST,
            port=RABBITMQ_PORT,
            credentials=credentials
        )
        
        connection = pika.BlockingConnection(parameters)
        channel = connection.channel()
        channel.queue_declare(queue='reviews_ozon', durable=True)
        channel.basic_publish(
            exchange='',
            routing_key='reviews_ozon',
            body=json.dumps(message),
            properties=pika.BasicProperties(delivery_mode=2))
        connection.close()
        return True
    except Exception as e:
        logger.error(f"RabbitMQ error: {e}")
        return False
