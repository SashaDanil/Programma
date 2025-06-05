# Сервис обработки отзывов

Сервис для автоматического сбора отзывов с Ozon и генерации ответов с использованием нейросети Yandex GPT.

## Требования

- Python 3.9+
- PostgreSQL
- RabbitMQ

## Установка и запуск

### Локальная установка

1. Клонировать репозиторий:
```
git clone <url репозитория>
cd reviews_service
```

2. Создать виртуальное окружение:
```
python -m venv venv
venv/Scripts/activate  # для Windows
source venv/bin/activate  # для Linux/Mac
```

3. Установить зависимости:
```
pip install -r requirements.txt
```

4. Создать файл `.env` на основе `.env.example`:
```
cp .env.example .env
```

5. Заполнить `.env` своими данными (API ключи, настройки БД)

6. Запустить API сервер:
```
uvicorn src.main:app --reload --port 8002
```
7. Запустить scheduler
```
python -m src.parcer.scheduler
```

## Структура проекта

- `/src` - исходный код приложения
  - `/api` - API эндпоинты
  - `/neural` - модули для работы с нейросетью
  - `/parcer` - модули для парсинга отзывов
  - `/schemas` - схемы данных Pydantic
  - `/utils` - вспомогательные утилиты
- `/logs` - директория для логов
- `.env` - переменные окружения
- `docker-compose.yml` - конфигурация Docker

## API документация

После запуска сервиса API документация доступна по URL:
- Swagger UI: http://localhost:8002/docs
- ReDoc: http://localhost:8002/redoc
