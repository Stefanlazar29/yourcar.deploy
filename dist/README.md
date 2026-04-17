# Mulberry Frontend (Vercel Deploy)

Acest folder conține doar fișierele necesare pentru deployment pe **Vercel** ca site static.

## Structura

- **HTML**: `mulberry.html`, `verify.html`, `index.html`, `login.html`
- **CSS**: `style.css` 
- **JS**: Toată logica frontend din `js/`
- **Assets**: Logo-uri, imagini din `assets/`

## Configurare

### 1. API Backend (Railway)
În `js/config.js`, URL-ul Railway este detectat automat:
```js
// Producție: https://mulberry-backend.up.railway.app
// Dev local: http://127.0.0.1:9000
```

### 2. Mock Data Fallback
Dacă Railway nu răspunde în 3 secunde, se încarcă date simulate din `js/mock_data.js`.

### 3. Domeniu Custom
În Vercel dashboard, conectează `mulberry.autos` la acest proiect.

## Deploy pe Vercel

1. **CLI**: `vercel --cwd dist`
2. **Git**: Conectează repo, setează Root Directory = `dist`
3. **Drag & Drop**: Trage folderul `dist` în Vercel dashboard

## QR Code Routing

`vercel.json` include rewrite pentru QR scanări:
```json
{
  "rewrites": [
    { "source": "/v/:unitId", "destination": "/verify.html?u=:unitId" }
  ]
}
```

Orice QR de forma `mulberry.autos/v/UNIT123` va deschide pagina de verificare.

## Status Check

În consolă (F12):
```js
checkApiHealth().then(console.log)
// → { ok: true, latency: 450, backend: "railway" }
```