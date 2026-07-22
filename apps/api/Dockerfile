# Gravity OS API — Render Docker runtime (ARCHITECTURE.md section 4)
FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

# Install dependencies first for layer caching.
COPY pyproject.toml ./
RUN pip install --upgrade pip && pip install .

# App source.
COPY app ./app

# Render provides $PORT at runtime.
ENV PORT=8000
EXPOSE 8000

CMD ["sh", "-c", "uvicorn app.main:app --host 0.0.0.0 --port ${PORT}"]
