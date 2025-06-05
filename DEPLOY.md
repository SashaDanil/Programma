# Инструкция по развертыванию сервиса reviews_service

## Необходимые компоненты
- Docker
- Docker Compose

## Подготовка к запуску

1. Клонируйте репозиторий на сервер:
```bash
git clone <ваш-репозиторий> reviews_service
cd reviews_service
```

2. Создайте файл `.env` с переменными окружения (все чувствительные данные хранятся в этом файле):
```bash
# Настройки для режима отладки
DEBUG=False
LOG_LEVEL=INFO

# Настройки базы данных PostgreSQL (замените на ваши значения)
POSTGRES_DB=reviews
POSTGRES_USER=Ilya
POSTGRES_PASSWORD=ilyailya228
POSTGRES_HOST=94.181.95.99
POSTGRES_PORT=5432
```

Важно: файл `.env` содержит чувствительные данные и не должен добавляться в систему контроля версий. 
Убедитесь, что он добавлен в `.gitignore`.

## Запуск сервиса

1. Запустите сервис с помощью Docker Compose:
```bash
docker-compose up -d
```

2. Проверьте, что сервис запущен:
```bash
docker-compose ps
```

## Управление контейнером

1. Для остановки контейнера:
```bash
docker-compose down
```

2. Для перезапуска контейнера:
```bash
docker-compose restart
```

3. Для обновления и перезапуска (после внесения изменений в код):
```bash
docker-compose down
docker-compose build
docker-compose up -d
```

4. Если вам нужно перезапустить контейнер после изменения переменных окружения:
```bash
docker-compose down
docker-compose up -d
```

5. Для просмотра логов в режиме реального времени:
```bash
docker-compose logs -f
```

## Автоматический запуск после перезагрузки сервера

Docker имеет встроенную поддержку автоматического перезапуска контейнеров. 
В нашем docker-compose.yml уже указан параметр `restart: always`, который гарантирует, 
что контейнер будет перезапущен при перезагрузке сервера.

Для проверки, что Docker запускается автоматически при загрузке системы:

```bash
sudo systemctl status docker
```

Если Docker не настроен на автозапуск, включите его:

```bash
sudo systemctl enable docker
```

## Устранение проблем с DNS

Если вы столкнулись с проблемами подключения к Docker Hub при сборке образа, попробуйте настроить DNS:

1. Настройте DNS для Docker:
```bash
sudo mkdir -p /etc/docker
sudo bash -c 'echo {"dns": ["8.8.8.8", "8.8.4.4"]} > /etc/docker/daemon.json'
sudo systemctl restart docker
```

2. Или настройте DNS на уровне системы (если /etc/resolv.conf - симлинк):
```bash
sudo rm /etc/resolv.conf
sudo bash -c 'echo "nameserver 8.8.8.8" > /etc/resolv.conf'
sudo bash -c 'echo "nameserver 8.8.4.4" >> /etc/resolv.conf'
```

## Проверка работоспособности

Вы можете проверить работоспособность API, отправив запрос к сервису:

```bash
curl http://localhost:8032/docs
```

## Логирование

Логи приложения сохраняются в каталоге `logs`, который подключен как том к контейнеру.
Вы также можете просмотреть логи контейнера с помощью команды:

```bash
docker-compose logs -f api
```

sudo systemctl restart docker
sudo systemctl status systemd-resolved
sudo systemctl enable --now systemd-resolved