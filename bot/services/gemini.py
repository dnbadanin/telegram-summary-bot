import logging

import google.generativeai as genai

from bot.config import GEMINI_API_KEY, GEMINI_MODEL

logger = logging.getLogger(__name__)

genai.configure(api_key=GEMINI_API_KEY)

_SYSTEM_PROMPT = """Ты — ассистент, который анализирует переписку в Telegram-чате и составляет краткое резюме за день.

Чат: {chat_title}
Дата: {date}
Количество сообщений: {count}

Сообщения:
{formatted_messages}

Задача:
1. Выдели 3–7 основных тем обсуждения.
2. Для каждой темы напиши краткое резюме (2–4 предложения).
3. Укажи ключевых участников обсуждения.
4. Отметь принятые решения или важные выводы, если они есть.
5. Используй Markdown: каждая тема — заголовок "## Тема: <название>".
6. Общая длина — до 3000 символов.
7. Пиши на русском языке."""

_NO_MESSAGES_TEXT = "Сообщений за указанный период не найдено."


async def generate_summary(
    chat_title: str,
    date_str: str,
    formatted_messages: str,
    message_count: int,
) -> str:
    if message_count == 0:
        return _NO_MESSAGES_TEXT

    prompt = _SYSTEM_PROMPT.format(
        chat_title=chat_title,
        date=date_str,
        count=message_count,
        formatted_messages=formatted_messages,
    )

    try:
        model = genai.GenerativeModel(GEMINI_MODEL)
        response = await model.generate_content_async(prompt)
        text = response.text.strip()
        logger.info("Gemini summary generated for %s (%d chars)", chat_title, len(text))
        return text
    except Exception as exc:
        logger.error("Gemini API error for chat %s: %s", chat_title, exc)
        raise
