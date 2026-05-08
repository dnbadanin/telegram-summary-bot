# Telegram Chat Summarizer Bot

Бот собирает сообщения из Telegram-групп, ежедневно генерирует краткое резюме на русском языке (с помощью Google Gemini) и рассылает его подписчикам в личные сообщения. Изображения и ссылки автоматически сохраняются на Яндекс.Диск.

---

## Деплой на VDS / VPS

### 1. Требования к серверу

- ОС: Ubuntu 22.04 / Debian 12 (или любой дистрибутив с Docker)
- RAM: 256 MB+
- Открытый исходящий интернет (для Telegram, Gemini, Яндекс.Диск)

### 2. Установка Docker

```bash
curl -fsSL https://get.docker.com | sh
sudo usermod -aG docker $USER
newgrp docker
```

Проверка:
```bash
docker --version
docker compose version
```

### 3. Клонирование репозитория

```bash
sudo git clone https://github.com/dnbadanin/telegram-summary-bot.git /opt/telegram-summary-bot
sudo chown -R $USER:$USER /opt/telegram-summary-bot
cd /opt/telegram-summary-bot
```

### 4. Настройка окружения

```bash
cp .env.example .env
nano .env
```

Заполните все поля (см. раздел [Конфигурация](#конфигурация-env) ниже).

### 5. Запуск

```bash
docker compose up -d
```

Просмотр логов:
```bash
docker compose logs -f bot
```

### 6. Добавьте бота в группу

1. Добавьте бота в группу/супергруппу.
2. Назначьте его **администратором** (минимум — право читать сообщения).

### 7. Подпишитесь на дайджест

1. Откройте личный диалог с ботом, отправьте `/start`.
2. Отправьте `/chats` — бот покажет список отслеживаемых чатов с их ID.
3. Отправьте `/subscribe -100123456789` (подставьте реальный ID чата).

### Управление

| Команда | Описание |
|---|---|
| `docker compose up -d` | Запустить в фоне |
| `docker compose down` | Остановить |
| `docker compose restart bot` | Перезапустить |
| `docker compose logs -f bot` | Следить за логами |
| `docker compose pull && docker compose up -d` | Обновить после изменений |

### Автозапуск при перезагрузке сервера

Политика `restart: unless-stopped` в `docker-compose.yml` уже обеспечивает автоматический перезапуск. Убедитесь, что Docker-демон запускается при старте системы:

```bash
sudo systemctl enable docker
```

---

## Локальный запуск (macOS / Linux)

### Требования

- Python 3.11+
- Docker Desktop (для запуска через Docker)

### Через Docker (рекомендуется)

```bash
cp .env.example .env
# заполните .env
docker compose up -d
```

### Без Docker (для разработки)

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
# заполните .env, укажите локальные пути для DATABASE_PATH и LOG_PATH
python -m bot.main
```

---

## Первоначальная настройка токенов

### Telegram Bot Token

1. Найдите [@BotFather](https://t.me/BotFather) в Telegram.
2. Отправьте `/newbot`, следуйте инструкциям.
3. Скопируйте токен вида `123456789:AAxxxxxx`.

### Отключение режима приватности

Без этого бот не сможет читать все сообщения группы (только команды).

1. В @BotFather: `/mybots` → выберите бота.
2. **Bot Settings** → **Group Privacy** → **Turn off**.

### Google Gemini API Key

Перейдите на [aistudio.google.com](https://aistudio.google.com/), создайте API-ключ.

### Яндекс.Диск OAuth Token

Перейдите на [yandex.com/dev/disk/poligon](https://yandex.com/dev/disk/poligon/), авторизуйтесь и получите OAuth-токен.

---

## Команды бота

### Личные сообщения

| Команда | Описание |
|---|---|
| `/start` | Приветствие и инструкции |
| `/subscribe <chat_id>` | Подписаться на дайджест чата |
| `/unsubscribe <chat_id>` | Отписаться |
| `/list` | Список активных подписок |
| `/chats` | Чаты, которые отслеживает бот |
| `/help` | Справка |

### Команды в группе (только для администраторов)

| Команда | Описание |
|---|---|
| `/enable_summary` | Публиковать дайджест в группе |
| `/disable_summary` | Отключить публикацию в группе |
| `/status` | Статус бота: кол-во сообщений, время последнего резюме |

### Как узнать chat_id

После добавления бота в группу напишите `/chats` в личном сообщении боту.

---

## Конфигурация (`.env`)

| Переменная | По умолчанию | Описание |
|---|---|---|
| `TELEGRAM_BOT_TOKEN` | — | Токен бота (обязательно) |
| `GEMINI_API_KEY` | — | Ключ Google Gemini (обязательно) |
| `GEMINI_MODEL` | `gemini-1.5-flash` | Модель Gemini |
| `YANDEX_DISK_TOKEN` | — | OAuth-токен Яндекс.Диска (обязательно) |
| `YANDEX_DISK_ROOT` | `/TelegramBot` | Корневая папка на Диске |
| `SUMMARY_TIME` | `21:00` | Время рассылки дайджеста |
| `TIMEZONE` | `Europe/Moscow` | Временная зона |
| `SUMMARY_WINDOW_HOURS` | `24` | Глубина анализа (часов) |
| `DATABASE_PATH` | `/app/data/bot.db` | Путь к БД |
| `LOG_LEVEL` | `INFO` | Уровень логирования |
| `LOG_PATH` | `/app/logs/bot.log` | Путь к файлу логов |
| `MESSAGE_RETENTION_DAYS` | `30` | Хранить сообщения N дней (0 = вечно) |

---

## Структура проекта

```
telegram-summary-bot/
├── bot/
│   ├── main.py              ← точка входа
│   ├── config.py            ← загрузка .env
│   ├── handlers/
│   │   ├── messages.py      ← сохранение сообщений, загрузка медиа
│   │   ├── commands.py      ← /start, /subscribe, ...
│   │   └── admin.py         ← команды для администраторов группы
│   ├── services/
│   │   ├── database.py      ← асинхронная работа с SQLite
│   │   ├── gemini.py        ← клиент Google Gemini
│   │   ├── yandex_disk.py   ← загрузка на Яндекс.Диск
│   │   ├── summarizer.py    ← генерация и доставка дайджеста
│   │   └── scheduler.py     ← планировщик (APScheduler)
│   └── utils/
│       ├── link_extractor.py
│       └── text_formatter.py
├── tests/
├── data/                    ← SQLite БД (примонтирован как volume)
├── logs/                    ← файлы логов (volume)
├── pending/                 ← файлы, ожидающие загрузки на Диск
├── .env.example
├── Dockerfile
└── docker-compose.yml
```

---

## Запуск тестов

```bash
pip install -r requirements.txt pytest pytest-asyncio
pytest tests/ -v
```

---

## Устранение неполадок

**Бот не видит сообщения в группе**
→ Убедитесь, что отключён Privacy Mode через @BotFather (`/mybots` → Bot Settings → Group Privacy → Turn off).

**Ошибки Yandex Disk 401**
→ Токен устарел. Обновите `YANDEX_DISK_TOKEN` в `.env`, затем `docker compose restart bot`.

**Дайджест не приходит**
→ Проверьте `SUMMARY_TIME` и `TIMEZONE` в `.env`. Убедитесь, что подписались через `/subscribe <chat_id>`.

**Контейнер не запускается**
→ Проверьте логи: `docker compose logs bot`. Убедитесь, что заполнены все три обязательных токена в `.env`.

**Бот перестал отвечать после перезагрузки сервера**
→ Выполните `sudo systemctl enable docker`, чтобы Docker стартовал автоматически.

---

## Правовые замечания

> Бот сохраняет все текстовые сообщения из групп в локальную базу данных, а изображения и ссылки — на Яндекс.Диск. Участники группы **должны быть уведомлены** об этом. Использование бота должно соответствовать законодательству вашей страны и [правилам Telegram](https://core.telegram.org/bots).
