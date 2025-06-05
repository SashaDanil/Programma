FROM python:3.11-slim

WORKDIR /app

# Копирование и установка зависимостей
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Копирование кода приложения
COPY . .

# Порт, который будет слушать контейнер
EXPOSE 8032

# Запуск приложения через Uvicorn
CMD ["uvicorn", "src.main:app", "--host", "0.0.0.0", "--port", "8032"] 