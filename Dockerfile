FROM python:3.11-slim

# 1. Устанавливаем системные зависимости (требует root)
RUN apt-get update && apt-get install -y --no-install-recommends \
    libgl1 \
    libglib2.0-0 \
    libzbar0 \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# 2. Копируем requirements и устанавливаем зависимости
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 3. Копируем исходный код
COPY src/ ./src/

# 4. Объединяем оставшиеся RUN: создание пользователя, смена владельца, переключение
RUN groupadd -r appuser && useradd -r -g appuser -m appuser && \
    chown -R appuser:appuser /app

# 5. Переключаемся на непривилегированного пользователя
USER appuser

EXPOSE 8080

CMD ["python", "src/main.py"]