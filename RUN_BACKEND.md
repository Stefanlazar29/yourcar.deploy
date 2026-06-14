# Pornire backend Mulberry (FastAPI)

Dacă în consolă vezi **`ERR_CONNECTION_REFUSED`** sau **`Failed to fetch`** către `http://127.0.0.1:9000`, **serverul Python nu rulează**.

---

## Pornire automată la login Windows (fără consolă vizibilă)

1. În proiect există **`START_MULBERRY_SILENT.vbs`** — pornește `uvicorn` cu fereastra ascunsă (`WindowStyle` 0).
2. **Win + R** → `shell:startup` → Enter.
3. În folderul Startup: click dreapta → **Nou** → **Shortcut**.
4. Țintă: `wscript.exe`  
   **Argumente:** `//nologo "C:\Users\Asus\Desktop\yourcar.deploy\START_MULBERRY_SILENT.vbs"`  
   (înlocuiește calea dacă proiectul nu e pe Desktop.)
5. **Nu copia** VBS-ul în Startup — scurtătura trebuie să indice fișierul din folderul proiectului (altfel `uvicorn` nu găsește `backend`).

**Manual (cu fereastră + pause):** `START_MULBERRY.bat` în proiect sau pe Desktop (vezi `START_MULBERRY.bat` pe Desktop cu aceeași comandă).

**Verificare după boot:** în browser deschide **http://127.0.0.1:9000/health** — trebuie să vezi `{"ok":true}`.

---

## Comanda corectă (Windows / PowerShell)

**Nu folosi** comanda scurtă `uvicorn ...` dacă primești:

```text
uvicorn : The term 'uvicorn' is not recognized...
```

Pe Windows, executabilul `uvicorn` nu e mereu în **PATH**. Folosește **modulul Python**:

```powershell
cd c:\Users\Asus\Desktop\yourcar.deploy
python -m uvicorn backend.main:app --reload --port 9000
```

**De ce funcționează:** `python -m uvicorn` pornește pachetul **uvicorn** din mediul Python curent, fără să caute un fișier `uvicorn.exe` separat.

Opțional (explicit host):

```powershell
python -m uvicorn backend.main:app --reload --host 127.0.0.1 --port 9000
```

---

## Plan B — dacă tot dă eroare

Lipsește pachetul în acest mediu Python. Instalează dependențele:

```powershell
pip install fastapi uvicorn
```

Sau din folderul proiectului (recomandat, cu tot ce trebuie pentru Mulberry):

```powershell
pip install -r backend/requirements.txt
```

Apoi repetă:

```powershell
python -m uvicorn backend.main:app --reload --port 9000
```

---

## Cum știi că a pornit (victoria)

Terminalul **nu** mai aruncă erori și apare linia de genul:

```text
INFO:     Uvicorn running on http://127.0.0.1:9000 (Press CTRL+C to quit)
```

---

## Live Server (port 5500) și CORS

Dacă deschizi `mulberry.html` prin **Live Server** (`http://127.0.0.1:5500`), backend-ul trebuie să permită originea respectivă. În `backend/main.py` sunt listate explicit `http://127.0.0.1:5500` și `http://localhost:5500` (împreună cu alte origini de dev). Pornește uvicorn **înainte** de login.

Opțional: dublu-click pe **`START_MULBERRY.bat`** (Desktop sau folder proiect).

---

## Verificare rapidă în browser

- **http://127.0.0.1:9000/health** → `{"ok":true}`
- **http://127.0.0.1:9000/debug/status** → utilizatori + mașini (SQLite)

## MiniMax / MulberryExoTerra (POST /chat)

1. Copiază `backend/.env.example` în `backend/.env`.
2. Pune cheia ta în `MINIMAX_API_KEY=` (fără spații după `=`).
3. Opțional: `AGENT_ID=MulberryEXO`, `MINIMAX_MODEL=M2-her`.
4. `pip install python-dotenv` (sau `pip install -r backend/requirements.txt`).
5. Repornește uvicorn.

Dashboard-ul (cardul Mulberry Assistant) trimite mesaje la `/chat` cu JWT-ul tău; backend-ul apelează MiniMax.

## Telemetrie erori (401 etc.)

Erorile 401 din frontend sunt trimise la `POST /log-error` și salvate în `backend/errors.log`.  
Poți spune Cursor: „Citește errors.log și repară codul care a cauzat aceste erori.”

## Teste (pytest)

```powershell
python -m pytest tests/test_auth.py -v
```

Verifică că login/register returnează JWT valid (prefix `eyJ`).

---

## Eroare 500 la înregistrare (Swagger / frontend)

Dacă primesti **500** când înregistrezi un utilizator:

1. **Verifică terminalul** unde rulează uvicorn — apare un traceback roșu. Dacă scrie `sqlite3.OperationalError: no such table: users` sau ceva similar, baza de date nu are tabelele corecte.

2. **Resetare completă:** oprește serverul (CTRL+C), apoi rulează:

   ```powershell
   .\reset_db.ps1
   ```

   Sau șterge manual `backend/dev.db` (dacă există), apoi repornește serverul.

3. **Hash parole:** proiectul folosește pachetul **`bcrypt`** direct (fără passlib), compatibil Python 3.12+ / 3.14:
   ```powershell
   pip install -r backend/requirements.txt
   ```

4. După restart, tabelele se recreează automat la pornire. Testează din nou înregistrarea.

---

## CORS

În `backend/main.py` este deja `CORSMiddleware` cu `allow_origins=["*"]`. Frontend-ul folosește **`js/config.js`** → `API_BASE_URL: 'http://127.0.0.1:9000'`.

---

## Ollama (separat, opțional)

```bash
ollama serve
```

---

**Notă:** Dacă ai mai multe instalări Python, folosește **`py -3.11 -m uvicorn ...`** sau **`python3 -m uvicorn ...`** în loc de `python`, ca să fii sigur că instalezi și rulezi în același mediu.
