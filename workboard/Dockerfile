FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    WORKBOARD_HOST=0.0.0.0 \
    WORKBOARD_PORT=5000 \
    WORKBOARD_AUTH_MODE=password \
    WORKBOARD_DATA_DIR=/app/data \
    WORKBOARD_DOCS_DIR=/app/data/docs

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY server.py .
COPY static ./static
RUN mkdir -p /app/data/docs/TODO /app/data/docs/Done

EXPOSE 5000
USER nobody
CMD ["python", "server.py"]

