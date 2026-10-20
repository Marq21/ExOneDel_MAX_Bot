# Используем официальный образ Python 3.11
FROM python:3.11-slim

# Устанавливаем рабочую директорию
WORKDIR /app

# Устанавливаем зависимости сначала для кэширования
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Копируем исходный код
COPY src/ ./src/

# Открываем порт, который будет слушать бот (мы укажем 8080)
EXPOSE 8080

# Команда запуска
CMD ["python", "src/main.py"]