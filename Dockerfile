FROM python:3.11-slim

RUN apt-get update && apt-get install -y --no-install-recommends \
    libgl1 \
    libglib2.0-0 \
    libzbar0 \
    && rm -rf /var/lib/apt/lists/*

RUN groupadd -r appuser && useradd -r -g appuser -m appuser

WORKDIR /app

ENV PYTHONPATH="/app"

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY src/ ./src/

RUN chown -R appuser:appuser /app

USER appuser

EXPOSE 8080

CMD ["python", "src/main.py"]