FROM python:3.13-slim AS builder

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt ./requirements.txt
RUN pip wheel --no-cache-dir --wheel-dir /wheels -r requirements.txt

COPY main.py config.py dependencies.py models.py cache_service.py helpers.py limiter.py requirements.txt ./
COPY routers ./routers
COPY services ./services
COPY jhora ./jhora


FROM python:3.13-slim AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

COPY --from=builder /wheels /wheels
COPY --from=builder /app/requirements.txt ./requirements.txt
RUN pip install --no-cache-dir --no-index --find-links=/wheels -r requirements.txt \
    && rm -rf /wheels

COPY --from=builder /app/main.py ./main.py
COPY --from=builder /app/config.py ./config.py
COPY --from=builder /app/dependencies.py ./dependencies.py
COPY --from=builder /app/models.py ./models.py
COPY --from=builder /app/cache_service.py ./cache_service.py
COPY --from=builder /app/helpers.py ./helpers.py
COPY --from=builder /app/limiter.py ./limiter.py
COPY --from=builder /app/routers ./routers
COPY --from=builder /app/services ./services
COPY --from=builder /app/jhora ./jhora

CMD ["sh", "-c", "uvicorn main:app --host 0.0.0.0 --port ${PORT:-8080}"]
