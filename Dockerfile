# syntax=docker/dockerfile:1.4
FROM python:3.11-slim

# 1. Системные пакеты с кэшем apt (не попадает в образ, живёт на хосте)
RUN --mount=type=cache,target=/var/cache/apt,sharing=locked \
    --mount=type=cache,target=/var/lib/apt,sharing=locked \
    apt-get update && apt-get install -y --no-install-recommends \
    libgl1 \
    libglib2.0-0 \
    libzbar0

# 2. Непривилегированный пользователь — до COPY, чтобы сразу отдать владение
RUN groupadd -r appuser && useradd -r -g appuser -m appuser

WORKDIR /app
ENV PYTHONPATH="/app"

# 3. Зависимости с кэшем pip (не попадает в образ)
COPY requirements.txt .
RUN --mount=type=cache,target=/root/.cache/pip \
    pip install -r requirements.txt

# 4. Код + владение за один шаг (без отдельного chown -R)
COPY --chown=appuser:appuser src/ ./src/

USER appuser
EXPOSE 8080
CMD ["python", "src/main.py"]