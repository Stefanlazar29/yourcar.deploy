# Mulberry — FastAPI (Railway, Fly.io, or any Docker host)
# Railway: conectează repo-ul, lasă detectarea Dockerfile; setează DATABASE_URL (ex. Supabase).

FROM python:3.11-slim-bookworm

WORKDIR /app

# Obligatoriu pentru `from backend import …` — rădăcina proiectului trebuie pe PYTHONPATH
ENV PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONPATH=/app

# Wheels pentru psycopg2-binary de obicei suficiente; build-essential pentru pachete fără wheel
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libpq-dev \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Instalare dependențe, apoi tot repo-ul (folderul backend/ la /app/backend — nu doar conținutul lui).
COPY backend/requirements.txt backend/requirements.txt
RUN pip install --upgrade pip && pip install -r backend/requirements.txt

COPY . .

EXPOSE 8080

# Railway injectează PORT; implicit 8000 pentru docker local
CMD ["sh", "-c", "exec uvicorn backend.main:app --host 0.0.0.0 --port ${PORT:-8080}"]
