# Mulberry — Docker (Hard-Shield P0)

## O singură comandă (server Linux / droplet)

```bash
cd /path/to/yourcar.deploy
cp deploy/.env.production.example .env
# Editează .env: JWT_SECRET, MLBR_SECRET, MULBERRY_CORS_ORIGINS=https://domeniul-tău

bash deploy/init_ssl_self_signed.sh   # sau pune certificat Let’s Encrypt în docker/nginx/ssl/
docker compose up -d --build
```

Aplicația: **https://&lt;server&gt;/** (Nginx termină TLS; API-ul rămâne pe rețeaua internă `api:8000`).

## Structură

| Fișier | Rol |
|--------|-----|
| `Dockerfile` | Imagine API + frontend static (Uvicorn :8000) |
| `docker-compose.yml` | `api` + `nginx` + `backup`, volum `mulberry_data` → `/data` |
| `Dockerfile.backup` | Job backup + VACUUM opțional |
| `docker/nginx/default.conf` | HTTPS, proxy către API |
| `deploy/.env.production.example` | Șablon secrete (copiat ca `.env`) |
| `scripts/mulberry_backup.py` | WAL checkpoint + `.backup` + upload S3 opțional |
| `deploy/init_ssl_self_signed.sh` | Cert self-signed pentru test |

## Secrete

- Nu comita `.env`. În producție: `JWT_SECRET`, `MLBR_SECRET`, chei API (`MINIMAX_API_KEY`, `GROQ_API_KEY`, …) doar în variabile de mediu (Compose / orchestrator).
- `MULBERRY_CORS_ORIGINS` — lista separată prin virgulă a originilor HTTPS permise (domeniul public al app-ului).

## HTTPS cu Let’s Encrypt (rezumat)

1. Montează `fullchain.pem` și `privkey.pem` în `docker/nginx/ssl/`.
2. Sau folosește certbot pe host și volume către același director.
3. Poți lăsa temporar doar HTTP pe port 80 comentând blocul `443` în `default.conf` — **nu recomandat pentru producție**.

## Backup SQLite

- Copii locale: `/data/backups/` pe volumul Docker (păstrate până la `BACKUP_KEEP_LOCAL`).
- S3 / DigitalOcean Spaces: setează `S3_BACKUP_BUCKET`, `AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY`, opțional `AWS_ENDPOINT_URL`.
- **VACUUM** săptămânal: `VACUUM_WEEKLY_ON_DAY=0` … `6` (0 = luni). Dezactivare: `-1` sau gol. Rulează pe fișierele live — evită traficul intens sau oprește API-ul scurt dacă apare blocare.

## Verificare

```bash
curl -sk https://localhost/health
docker compose logs -f api
```

## Dezvoltare locală fără Docker

Rămâne valid: `python -m uvicorn backend.main:app --host 127.0.0.1 --port 9000` și `RUN_BACKEND.md`.
