FROM python:3.11-slim

WORKDIR /app

RUN addgroup --system botgroup && adduser --system --ingroup botgroup botuser

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY bot/ ./bot/

RUN mkdir -p /app/data /app/logs /app/pending \
    && chown -R botuser:botgroup /app

USER botuser

CMD ["python", "-m", "bot.main"]
