# Mulberry — FastAPI (Railway, Fly.io, or any Docker host)
# Railway: conectează repo-ul, lasă detectarea Dockerfile; setează DATABASE_URL (ex. Supabase).

FROM python:3.11-slim-bookworm

WORKDIR /app

ENV PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PYTHONDONTWRITEBYTECODE=1

# Wheels pentru psycopg2-binary de obicei suficiente; build-essential pentru pachete fără wheel
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libpq-dev \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Instalare doar din backend/requirements.txt — nu depinde de requirements.txt la rădăcină
# (evită crash Railway dacă acel fișier lipsește din repo sau din contextul de build).
COPY backend/requirements.txt backend/requirements.txt

RUN pip install --upgrade pip && pip install -r backend/requirements.txt

COPY . .

EXPOSE 8080

# Railway injectează PORT; implicit 8000 pentru docker local
CMD ["sh", "-c", "exec uvicorn backend.main:app --host 0.0.0.0 --port ${PORT:-8080}"]
