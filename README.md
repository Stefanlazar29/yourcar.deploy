# Mulberry 
**Co-pilot for your vehicle · by ExoTerra**

>  **Transparency notice:** Mulberry was built with significant AI assistance (Claude, Cursor). The codebase reflects a product vision and deployment experience, not standalone engineering authorship. The demonstrable technical skill here is Linux server deployment, Docker orchestration, and FastAPI backend setup.

---

## What is Mulberry?

Mulberry is a B2B2C automotive platform designed to bring transparency to the used car market. The core thesis: a vehicle's true value should be verifiable, not estimated.

**The problem it addresses:**
- Used car buyers have no reliable, real-time source of vehicle history and condition scoring
- Dealers lack a standardized digital identity system for their inventory
- The market runs on information asymmetry — sellers know more than buyers

**The solution:**
A vehicle identity and scoring platform where every car has a verifiable digital profile, accessible via QR code, with a market-validated condition score.

---

## Business Model

**B2B2C subscription tiers:**

| Tier | Target | Price | Features |
|------|--------|-------|----------|
| Basic | Private owners | Free | Mulberry ID, basic SoftScore |
| Pro | Enthusiasts | ~5€/month | Full SoftScore, cloud documents, AI assistant |
| Dealer | Car dealerships | ~49€/month | Fleet management, bulk QR generation, B2B reports |
| Enterprise | Platforms / insurers | Custom | API access, white-label, data feeds |

---

## Core Features

### Mulberry ID
Every vehicle gets a unique digital identity — a signed QR code linking to its profile. Scannable by anyone, owned by the user.

### SoftScore
A proprietary vehicle condition index calculated from:
- Service history documents
- ITP / RCA expiry dates
- Mileage and age
- Accident history
- AI-assisted document analysis

Expressed as a percentage with an estimated market value range.

### Mulberry Cloud
Secure document storage for vehicle-related files: RCA, ITP, service records, purchase invoices. Documents feed into SoftScore automatically.

### Mulberry Assistant
An AI co-pilot (powered by Groq / Llama) that answers vehicle-specific questions, interprets DTC codes, and provides maintenance guidance based on the vehicle's actual profile.

### Mulberry EXO (Notification Engine)
Proactive alerts for expiring documents, upcoming maintenance, and market value changes. Scheduled via APScheduler.

---

## Technical Stack

| Layer | Technology |
|-------|-----------|
| Backend | FastAPI (Python) |
| Database | SQLite (dev) / PostgreSQL (prod roadmap) |
| AI | Groq API — llama-3.3-70b-versatile |
| Frontend | Vanilla JS, HTML, CSS |
| Infrastructure | Docker, Nginx, Hetzner VPS |
| Auth | JWT token-based, email + password |

---

## Deployment

Self-hosted on a Hetzner VPS running Ubuntu 24.

```
Docker services:
├── mulberry-api      FastAPI backend (port 10000)
├── mulberry-nginx    Static frontend + reverse proxy (port 8080)
└── mulberry-backup   SQLite backup service
```

Live at: `http://46.225.100.151:8080/mulberry.html`

---

## Market Validation Thesis

The automotive transparency market is growing. Reference points:
- **Carfax / AutoCheck** (US) — billion-dollar businesses built on vehicle history
- **AutoScout24 / Mobile.de** — marketplaces that lack integrated condition scoring
- **Carte Grise / RAR** (Romania) — government data that is not consumer-accessible

Mulberry's differentiation: real-time scoring + document verification + AI assistant in a single mobile-first interface, at a price accessible to private owners, not just dealers.

---

## Status

 **MVP — in active development**

- [x] Vehicle onboarding flow
- [x] Mulberry ID + QR generation
- [x] SoftScore calculation engine
- [x] Cloud document storage
- [x] AI assistant integration
- [x] Server deployment (Docker + Nginx)
- [ ] Payment / subscription system
- [ ] Dealer dashboard
- [ ] Public API

---

## Contact

Built by Stefan Lazar · ExoTerra
