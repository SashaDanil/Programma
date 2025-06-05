# src/config.py
import os
from pathlib import Path
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.exc import SQLAlchemyError

# 1. Сначала объявляем ВСЕ константы, которые могут понадобиться другим модулям
BASE_DIR = Path(__file__).parent.parent
SRC_DIR = Path(__file__).parent
LOG_DIR = BASE_DIR / 'logs'
LOG_DIR.mkdir(exist_ok=True)
LOG_FILE = LOG_DIR / 'ozon_reviews.log'
LAST_ID_FILE = SRC_DIR / 'parcer' / 'last_id.txt'

# 2. Базовые настройки (не требующие импортов)
DEBUG = os.getenv("DEBUG", "False").lower() == "true"
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")
SCHEDULE_INTERVAL = int(os.getenv('SCHEDULE_INTERVAL', '1'))

# 3. Настройки БД (без импорта моделей!)
DB_CONFIG = {
    'dbname': os.getenv('POSTGRES_DB', 'reviews'),
    'user': os.getenv('POSTGRES_USER', 'Ilya'),
    'password': os.getenv('POSTGRES_PASSWORD', 'ilyailya228'),
    'host': os.getenv('POSTGRES_HOST', '94.181.95.99'),
    'port': os.getenv('POSTGRES_PORT', '5432')
}

DATABASE_URL = f"postgresql://{DB_CONFIG['user']}:{DB_CONFIG['password']}@{DB_CONFIG['host']}:{DB_CONFIG['port']}/{DB_CONFIG['dbname']}"

# 4. Создаем движок и сессию (лениво)
_engine = None
_SessionLocal = None


def get_db_session():
    global _engine, _SessionLocal
    if _engine is None:
        _engine = create_engine(DATABASE_URL)
        _SessionLocal = sessionmaker(bind=_engine)
    return _SessionLocal()


# 5. Статичные конфиги
API_ENDPOINTS = {
    'process_reviews': 'http://127.0.0.1:8002/process_unprocessed_reviews',
    'process_reviews_with_responses': 'http://127.0.0.1:8002/process_reviews_with_responses'
}

OZON_API_URLS = {
    'review_list': 'https://api-seller.ozon.ru/v1/review/list',
    'review_info': 'https://api-seller.ozon.ru/v1/review/info',
    'review_comments': 'https://api-seller.ozon.ru/v1/review/comment/list',
    'product_info': 'https://api-seller.ozon.ru/v3/product/info/list'
}


# 6. Функция для получения ключей (с твоей логикой)
def get_api_keys():
    from src.models import ApiKeys  # Ленивый импорт модели
    import os
    from sqlalchemy.exc import SQLAlchemyError

    db = get_db_session()
    try:
        # Получаем все записи из таблицы api_keys
        all_keys = db.query(ApiKeys).all()

        # Преобразуем каждую запись в словарь с ключами
        result = [
            {
                'id': key.id,
                'YANDEX_GPT_API_KEY': key.YANDEX_GPT_API_KEY or os.getenv('YANDEX_GPT_API_KEY'),
                'OZON_API_KEY': key.OZON_API_KEY or os.getenv('OZON_API_KEY'),
                'OZON_CLIENT_ID': key.OZON_CLIENT_ID or os.getenv('OZON_CLIENT_ID')
            }
            for key in all_keys
        ]

        # Если таблица пустая, возвращаем хотя бы один набор из .env
        if not result:
            result.append({
                'id': None,
                'YANDEX_GPT_API_KEY': os.getenv('YANDEX_GPT_API_KEY'),
                'OZON_API_KEY': os.getenv('OZON_API_KEY'),
                'OZON_CLIENT_ID': os.getenv('OZON_CLIENT_ID')
            })

        return result

    except SQLAlchemyError as e:
        print(f"Ошибка БД: {e}")
        # Fallback на .env если БД недоступна
        return [{
            'id': None,
            'YANDEX_GPT_API_KEY': os.getenv('YANDEX_GPT_API_KEY'),
            'OZON_API_KEY': os.getenv('OZON_API_KEY'),
            'OZON_CLIENT_ID': os.getenv('OZON_CLIENT_ID')
        }]
    finally:
        db.close()

headers = {
                'accept': 'application/json, text/plain, */*',
                'accept-language': 'ru',
                'content-type': 'application/json',
                'origin': 'https://seller.ozon.ru',
                'priority': 'u=1, i',
                'referer': 'https://seller.ozon.ru/app/reviews?__rr=1',
                'sec-ch-ua': '"Microsoft Edge";v="135", "Not-A.Brand";v="8", "Chromium";v="135"',
                'sec-ch-ua-mobile': '?1',
                'sec-ch-ua-platform': '"Android"',
                'sec-fetch-dest': 'empty',
                'sec-fetch-mode': 'cors',
                'sec-fetch-site': 'same-origin',
                'user-agent': 'Mozilla/5.0 (Linux; Android 6.0; Nexus 5 Build/MRA58N) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/135.0.0.0 Mobile Safari/537.36 Edg/135.0.0.0',
                'x-o3-app-name': 'seller-ui',
                'x-o3-company-id': 123,
                'x-o3-language': 'ru',
                'x-o3-page-type': 'review',
            }

# 7. Инициализация ключей при старте
api_keys_data = get_api_keys()