# Deploy Railway (fără Docker)

## ✅ Curățenia completă

- **Șters**: `Dockerfile`, `docker-compose.yml`, `railway.toml`
- **Adăugat**: `main.py` (PORT din Railway), `Procfile`, `runtime.txt`, `railway.toml` (start + healthcheck `/health`)

## 🚀 Cum funcționează acum

### 1. **Local Development**
```bash
# Start server (fără Live Server)
python main.py

# Browser: http://127.0.0.1:9000/mulberry.html
# API health: http://127.0.0.1:9000/health
```

Sau dublu-click pe `START_LOCAL_DEV.bat`.

### 2. **Railway Deploy**
```bash
git add .
git commit -m "Remove Docker, use Nixpacks"
git push
```

Railway va detecta automat:
- `requirements.txt` → instalează dependențele Python
- `main.py` → entry point pentru server
- `Procfile` → comanda de start (`web: python main.py`)
- `runtime.txt` → versiunea Python (3.11.9)

### 3. **Baza de date**
- **Prod**: `/data/mulberry.db` (volum persistent Railway)
- **Local**: `./data/mulberry.db` (creat automat)
- **Backup**: Rămâne în același loc → **zero pierderi de date**

## 📁 Structura simplificată

```
yourcar.deploy/
├── main.py              # Entry point Railway
├── requirements.txt     # Dependențe Python
├── Procfile            # "web: python main.py"
├── runtime.txt         # "python-3.11.9"
├── backend/            # API FastAPI
│   ├── main.py         # App-ul principal
│   └── requirements.txt # Dependențe backend
├── js/                 # Frontend JavaScript
├── assets/             # Imagini, logo-uri
└── *.html             # Pagini statice
```

## ⚡ Avantaje Nixpacks vs Docker

| Aspect | Docker | Nixpacks |
|--------|--------|----------|
| **Build time** | 3-5 min | 30-60s |
| **Deploy speed** | Lent | Rapid |
| **Debug** | Logs obscuri | Erori clare Python |
| **Baza de date** | Volum mount complex | Simplu `/data` |

## 🔧 Variables Railway

Railway setează automat:
- `PORT` → detectat de `main.py`
- Volum `/data` → pentru SQLite persistent

**Fără configurare manuală necesară!**

## ✨ Test rapid

După deploy:
```bash
curl https://yourapp.railway.app/health
# → {"ok":true}
```

Browser: `https://yourapp.railway.app/mulberry.html`