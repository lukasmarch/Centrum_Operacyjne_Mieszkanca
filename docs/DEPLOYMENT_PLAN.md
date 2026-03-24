# Plan Wdrożenia Produkcyjnego - Centrum Operacyjne Mieszkańca

## Kontekst

Aplikacja "Centrum Operacyjne Mieszkańca" (portal informacyjny gminy Rybno) działa lokalnie na środowisku deweloperskim. Celem jest wdrożenie na serwer produkcyjny z domeną, HTTPS, automatycznym CI/CD i strategią backup. Wymagania: niski koszt (projekt gminny), skalowalność bazy danych (pgvector rośnie), niezawodność schedulera (13 jobów), obsługa SSE streaming i PWA z push notifications.

---

## 1. Architektura Produkcyjna

```
[Użytkownicy]
      |
      v
[Cloudflare DNS + CDN]
      |
      +---> [Cloudflare Pages] ─── frontend (SPA + PWA)
      |            |
      |            | VITE_API_URL = https://api.centrum-mieszkanca.pl/api
      |            v
      +---> [Hetzner VPS CX22]
                   |
                   +── [Caddy] :443 → reverse proxy + auto SSL
                   |      |
                   |      +── /api/* → FastAPI :8000
                   |      +── /uploads/* → static files
                   |
                   +── [FastAPI + Uvicorn] :8000 (--workers 1)
                   |      +── APScheduler (13 jobów in-process)
                   |      +── SSE streaming (/api/chat/message)
                   |
                   +── [PostgreSQL 16 + pgvector] :5432
                          +── 30 tabel, IVFFlat index
                          +── BM25 tsvector hybrid search
```

**Dlaczego `--workers 1`**: APScheduler `BackgroundScheduler` działa in-process. Przy `workers > 1` każdy worker uruchomiłby osobny scheduler = duplikacja 13 jobów. FastAPI obsługuje współbieżność przez async I/O.

---

## 2. Backend - Serwery (3 warianty)

### Wariant A: Budżetowy (START) - **~20 EUR/mies.**

| Element | Rozwiązanie | Koszt |
|---------|------------|-------|
| VPS | **Hetzner CX22** (2 vCPU, 4GB RAM, 40GB NVMe) | 5,39 EUR |
| Lokalizacja | Falkenstein/Norymberga (DE) ~15ms do PL | - |
| Backup storage | Hetzner Volume 20GB | 1,72 EUR |
| Frontend | Cloudflare Pages (darmowy) | 0 EUR |
| DNS + CDN | Cloudflare (darmowy) | 0 EUR |
| SSL | Let's Encrypt via Caddy (auto) | 0 EUR |
| Domena | OVH.pl `.pl` (12,99 PLN/rok) | ~1 EUR |
| Monitoring | UptimeRobot (darmowy, 50 monitorów) | 0 EUR |
| AI API (OpenAI + Gemini) | ~100 art/dzień + chat | ~12 EUR |
| **RAZEM** | | **~20 EUR/mies.** |

**Dlaczego Hetzner**: Najlepsza cena/wydajność w EU, centra danych w Niemczech (najbliżej PL z tanich opcji), GDPR-compliant, 20TB transferu w cenie.

### Wariant B: Optymalny (PO 6 MIESIĄCACH) - **~35 EUR/mies.**

| Element | Rozwiązanie | Koszt |
|---------|------------|-------|
| VPS | **Hetzner CX32** (4 vCPU, 8GB RAM, 80GB NVMe) | 9,59 EUR |
| Backup VPS | Hetzner Backup Service (snapshoty) | 1,92 EUR |
| Offsite backup | Hetzner Storage Box 100GB | 3,81 EUR |
| Frontend + DNS | Cloudflare Pages + DNS | 0 EUR |
| Domena | `.pl` | ~1 EUR |
| AI API | wzrost użycia | ~18 EUR |
| **RAZEM** | | **~35 EUR/mies.** |

### Wariant C: Enterprise (SKALOWANIE) - **~70 EUR/mies.**

| Element | Rozwiązanie | Koszt |
|---------|------------|-------|
| VPS | **Hetzner CX42** (8 vCPU, 16GB RAM, 160GB) | 18,59 EUR |
| Managed DB | **Supabase Pro** (pgvector, 8GB, auto-backup) | ~23 EUR |
| Lub | **DigitalOcean Managed PostgreSQL** (Frankfurt) | ~14 EUR |
| Backup + CDN | Hetzner + Cloudflare | ~6 EUR |
| AI API | duży ruch | ~25 EUR |
| **RAZEM** | | **~65-75 EUR/mies.** |

### Alternatywne serwery backend (porównanie)

| Provider | Lokalizacja | RAM/CPU | Cena | pgvector | Uwagi |
|----------|------------|---------|------|----------|-------|
| **Hetzner CX22** | DE (Falkenstein) | 4GB/2vCPU | 5,39 EUR | self-managed | Najlepszy stosunek cena/jakość |
| DigitalOcean Basic | Frankfurt | 4GB/2vCPU | 24 USD | managed opcja | Droższy, lepszy panel |
| OVHcloud VPS | Warszawa | 4GB/2vCPU | 8,22 EUR | self-managed | DC w Polsce! |
| Vultr Cloud | Frankfurt | 4GB/2vCPU | 24 USD | self-managed | Dobry, droższy |
| AWS EC2 t3.medium | Frankfurt | 4GB/2vCPU | ~34 USD (RI) | RDS z pgvector | Enterprise, skomplikowany |
| Mikr.us | Polska | 2GB/1vCPU | 65 PLN/rok | self-managed | Ultra tani, mała moc |

---

## DODATEK: Analiza Hostinger i Render (dane z marca 2026)

### Hostinger VPS — pełny cennik i porównanie

**Hostinger VPS KVM (AMD EPYC, NVMe SSD, 1 Gbps, root access, DDoS protection):**

| Plan | vCPU | RAM | NVMe | Transfer | Cena/mies. (1 rok) | Cena/mies. (miesięczna) |
|------|------|-----|------|----------|--------------------|-----------------------|
| KVM 1 | 1 | 4 GB | 50 GB | 4 TB | ~$8.49 | ~$13.99 |
| **KVM 2** | **2** | **8 GB** | **100 GB** | **8 TB** | **~$11.49** | **~$17.99** |
| KVM 4 | 4 | 16 GB | 200 GB | 16 TB | ~$15.99 | ~$25.99 |
| KVM 8 | 8 | 32 GB | 400 GB | 32 TB | ~$25.99 | ~$38.99 |

**DC w EU**: Holandia (Amsterdam), **Litwa (Wilno ~400km od Warszawy)**, Niemcy.

| Cecha | Hostinger KVM 1 | Hetzner CX22 | Werdykt |
|-------|----------------|--------------|---------|
| **Cena (stała)** | **$8.49/mies. (1yr)** ~7.50 EUR | **5,39 EUR/mies.** | Hetzner **~30% tańszy** |
| **RAM / CPU** | 4GB / 1 vCPU | 4GB / 2 vCPU | **Hetzner** (2x więcej CPU!) |
| **Dysk** | **50GB NVMe** | 40GB NVMe | Hostinger (+10GB) |
| **Transfer** | 4 TB | **20 TB** | **Hetzner** (5x więcej!) |
| **DC blisko PL** | **Litwa** (~15ms) | Niemcy (~20ms) | Hostinger bliżej |
| **Docker/pgvector** | Tak (root) | Tak (root) | Remis |
| **Panel** | hPanel (przyjazny) | Minimalistyczny | Hostinger łatwiejszy |
| **Cena stała?** | Tak (1yr term) | **Tak (zawsze)** | Hetzner przewidywalny |
| **GDPR** | EU (Litwa) | EU (Niemcy) | Oba OK |

**Wniosek Hostinger**: Porównywalny z Hetzner, ale **~30% droższy** za gorszą specyfikację (1 vCPU vs 2, 4TB vs 20TB transfer). KVM 2 ($11.49) daje więcej RAM (8GB) i dysku (100GB) ale kosztuje **2x więcej niż Hetzner**. Plusy: DC w Litwie bliżej PL, łatwiejszy panel.

**Hostinger nadaje się gdy**: wolisz łatwiejszy panel zarządzania, cenisz DC bliżej Polski (Litwa), akceptujesz ~30% wyższy koszt.

### Render — ZNACZNIE DROŻSZY (nie rekomendowany)

**Render Web Services (backend FastAPI):**

| Plan | RAM | vCPU | Cena/mies. | Uwagi |
|------|-----|------|-----------|-------|
| Free | 512 MB | 0.1 | $0 | **Usypia po 15 min!** |
| Starter | 512 MB | 0.5 | **$7** | Always-on, ale 512MB = ryzykowne |
| **Standard** | **2 GB** | **1** | **$25** | **Minimum na produkcję** |
| Pro | 4 GB | 2 | $85 | Nadmiarowy |

**Render PostgreSQL (compute + storage osobno):**

| Instance | RAM | Compute/mies. | Storage |
|----------|-----|--------------|---------|
| Basic-256mb | 256 MB | ~$7 | +$0.30/GB/mies. |
| **Basic-1gb** | **1 GB** | **~$20** | **+$0.30/GB/mies.** |
| Standard-4gb | 4 GB | ~$95 | +$0.30/GB/mies. |

**pgvector**: Tak, wspierany natywnie (oficjalnie od 2023).
**Region EU**: Frankfurt (Niemcy) — dostępny.
**Static Sites**: Darmowe (CDN, SSL, auto-deploy z Git).

**Koszt produkcyjny Render:**

| Scenariusz | Backend | PostgreSQL | Frontend | RAZEM |
|-----------|---------|-----------|----------|-------|
| **Minimum (ryzykowne)** | Starter $7 (512MB!) | Basic-256mb $7 + $3 storage | Free | **~$17/mies.** |
| **Realny produkcyjny** | Standard $25 | Basic-1gb $20 + $3 storage | Free | **~$48/mies.** |

**Krytyczne problemy Render dla naszego projektu:**

1. **APScheduler + Free/Starter = PROBLEM**: Free tier usypia po 15 min. Starter (512MB) jest always-on, ale 512MB RAM to ryzyko przy FastAPI + APScheduler + OpenAI SDK jednocześnie.

2. **Koszt 2-8x wyższy**: Realny stack ($48/mies.) vs Hetzner all-in-one ($6/mies.). Nawet minimum ($17) jest droższe niż Hetzner.

3. **Ephemeral filesystem**: Pliki uploadowane (raporty: `backend/uploads/reports/`) **znikają po każdym deploy/restart**. Potrzeba Render Disk ($0.25/GB/mies.) lub migracja na S3/R2 — dodatkowy koszt i refaktoring kodu (`StaticFiles` mount → S3 presigned URLs).

4. **Zalety Render**: Zero-config deploy, managed SSL, auto-scaling, pgvector out-of-the-box. Ale Cloudflare Pages (frontend) + Caddy (backend SSL) dają to samo za darmo na VPS.

### Podsumowanie: Hostinger vs Render vs Hetzner

| | Hetzner CX22 | Hostinger KVM1 | Render (realny prod.) |
|--|-------------|---------------|----------------------|
| **Infra koszt/mies.** | **~6 EUR** | ~8 EUR | **~$48 (44 EUR)** |
| **Total z AI API** | **~20 EUR** | ~22 EUR | **~60 EUR** |
| **vCPU / RAM** | 2 / 4GB | 1 / 4GB | 1 / 2GB |
| **Dysk** | 40GB NVMe | 50GB NVMe | ephemeral! |
| **Transfer** | **20 TB** | 4 TB | bez limitu |
| **APScheduler** | Działa | Działa | Wymaga Standard ($25) |
| **pgvector** | Self-managed | Self-managed | Managed (wbudowany) |
| **DC blisko PL** | Niemcy (~20ms) | **Litwa (~15ms)** | Frankfurt (~10ms) |
| **File uploads** | Trwałe | Trwałe | **NIETRWAŁE** |
| **Docker** | Tak | Tak | Nie (PaaS) |
| **Łatwość** | Wymaga umiejętności | Łatwiejszy panel | Najłatwiejszy deploy |
| **Cena stała?** | **Tak** | Tak (1yr term) | Tak |
| **Rekomendacja** | **NAJLEPSZY WYBOR** | Dobra alternatywa | Zbyt drogi |

**FINALNA REKOMENDACJA**:
- **Hetzner CX22** (~20 EUR/mies. total) — najlepszy stosunek cena/jakość, stała cena, 20TB transferu, pełna kontrola
- **Hostinger KVM1** (~22 EUR/mies.) — akceptowalna alternatywa, DC bliżej Polski (Litwa), łatwiejszy panel, ale mniej CPU i transferu
- **Render** (~60 EUR/mies.) — **3x droższy**, wymaga refaktoringu file uploads, wart rozważenia tylko gdy zero-ops jest priorytetem ponad budżet

---

## 3. Baza Danych - Strategia Skalowania

### Obecny stan
- 30 tabel, ~500MB danych
- 170 chunków w `document_embeddings` (docelowo 10k+)
- IVFFlat index (cosine, 100 lists) na embeddingach 1536-dim
- BM25 tsvector + GIN index na hybrid search
- Async via asyncpg, pool_pre_ping=True

### Ścieżka skalowania

| Etap | Embeddingi | Rozmiar DB | Rozwiązanie |
|------|-----------|------------|-------------|
| Start | ~170 | ~500 MB | PostgreSQL na VPS (Hetzner CX22, 4GB) |
| 6 mies. | ~2 000 | ~1-2 GB | Ten sam VPS, tuning IVFFlat lists=50 |
| 1 rok | ~10 000 | ~5-8 GB | Upgrade do CX32 (8GB), osobny Volume |
| 2+ lata | ~50 000+ | ~15-20 GB | Dedicated server lub managed DB (Supabase) |

### Managed PostgreSQL z pgvector (opcje)

| Provider | pgvector | Cena/mies. | Lokalizacja | Auto-backup |
|----------|----------|-----------|-------------|-------------|
| **Supabase Pro** | Tak | 25 USD | Frankfurt | Tak (7 dni) |
| **DigitalOcean** | Tak | 15 USD | Frankfurt | Tak (7 dni) |
| **Neon Pro** | Tak | 19 USD | Frankfurt | Tak |
| AWS RDS | Tak (v0.5+) | ~25 USD | Frankfurt | Tak |
| Aiven | Tak | 29 USD | EU | Tak |

**Rekomendacja na start**: Self-managed na VPS (pełna kontrola, tańsze). Po roku rozważyć managed DB gdy rozmiar przekroczy 8GB.

### Backup bazy danych

```bash
# Codziennie o 4:00 (przed pipeline 6:00)
0 4 * * * pg_dump -Fc centrum_operacyjne > /backups/db/centrum_$(date +\%Y\%m\%d).dump

# Retencja: 14 dni lokalnie
0 5 * * * find /backups/db/ -name "*.dump" -mtime +14 -delete

# Tygodniowo offsite (Hetzner Storage Box)
0 3 * * 0 rclone copy /backups/db/ storagebox:centrum-backups/ --max-age 7d
```

---

## 4. Frontend - Hosting i Publikacja

### Rekomendacja: **Cloudflare Pages** (darmowy)

| Cecha | Cloudflare Pages | Vercel | Netlify |
|-------|-----------------|--------|---------|
| Cena | **Darmowy** (unlimited) | Darmowy (100GB/mies.) | Darmowy (100GB/mies.) |
| Bandwidth | **Nieograniczony** | 100 GB | 100 GB |
| CDN PoP w Polsce | **Warszawa** | Frankfurt | Frankfurt |
| Build min/mies. | 500 | 6000 | 300 |
| Custom domain | Tak | Tak | Tak |
| HTTPS | Auto | Auto | Auto |
| PWA/SW support | Tak | Tak | Tak |

**Dlaczego Cloudflare Pages**: Nieograniczony bandwidth (darmowy!), PoP w Warszawie (najniższy latency dla polskich użytkowników), natywna integracja z Cloudflare DNS.

### Konfiguracja Cloudflare Pages

```
Project name: centrum-mieszkanca
Production branch: main
Build command: cd frontend && npm install && npm run build
Output directory: frontend/dist

Environment variables:
  VITE_API_URL = https://api.centrum-mieszkanca.pl/api
  NODE_VERSION = 20
```

### Problemy do naprawy PRZED deployem frontendu

1. **Tailwind CDN** (`index.html:8`): `<script src="https://cdn.tailwindcss.com">` - to ~300KB JS parsowany runtime. Na produkcji MUSI być zastąpiony bundlowanym Tailwind CSS (~15-30KB po purge).
2. **Importmap esm.sh** (`index.html:66-75`): React/Recharts ładowane z CDN. Vite build powinien to nadpisywać (bundluje z node_modules), ale trzeba zweryfikować `dist/index.html`.
3. **Leaflet CSS** (`index.html:9`): CDN unpkg.com - działa, ale lepiej self-hostować lub dodać do bundla.

---

## 5. Domena

### Opcje domen

| Domena | Registrar | Cena/rok | Uwagi |
|--------|-----------|----------|-------|
| `centrum-mieszkanca.pl` | OVH.pl | 12,99 PLN (~3 EUR) | Najtańszy .pl |
| `centrum-mieszkanca.pl` | home.pl | 29 PLN (~7 EUR) | Polskie wsparcie |
| `centrum-mieszkanca.pl` | nazwa.pl | 49 PLN (~12 EUR) | Premium registrar |
| `centrum-mieszkanca.com` | Cloudflare Registrar | 10,11 USD | At-cost (bez marży) |
| `centrum.gminarybno.pl` | *subdomena urzędu* | **Darmowa** | Oficjalna wiarygodność! |

**Najlepsza opcja**: Jeśli gmina posiada domenę `gminarybno.pl` - użyć subdomeny `centrum.gminarybno.pl` (darmowa, oficjalna). W przeciwnym razie: `centrum-mieszkanca.pl` z OVH.pl.

### Konfiguracja DNS (Cloudflare)

```
Type   | Name  | Content                              | Proxy
-------+-------+--------------------------------------+-------
A      | api   | <IP_VPS_HETZNER>                     | DNS only*
CNAME  | @     | centrum-mieszkanca.pages.dev         | Proxied
CNAME  | www   | centrum-mieszkanca.pages.dev         | Proxied
```

*`api` musi być "DNS only" (szara chmurka) - Cloudflare proxy buforuje SSE streaming i dodaje latency do czatu.

### SSL/TLS

- **Frontend**: Automatyczny SSL od Cloudflare (darmowy)
- **Backend API**: Let's Encrypt via **Caddy** (zero-config, auto-renewal)
- Push notifications WYMAGAJĄ HTTPS (Web Push standard)

---

## 6. Docker Compose - Produkcja

### Nowe pliki do stworzenia

**`docker-compose.prod.yml`** (główny plik produkcyjny):

```yaml
version: '3.8'

services:
  db:
    image: pgvector/pgvector:pg16
    restart: always
    environment:
      POSTGRES_USER: ${DB_USER}
      POSTGRES_PASSWORD: ${DB_PASSWORD}
      POSTGRES_DB: centrum_operacyjne
    volumes:
      - pgdata:/var/lib/postgresql/data
    # Port 5432 NIE wystawiony na zewnątrz (tylko wewnętrzna sieć Docker)
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U ${DB_USER}"]
      interval: 10s
      timeout: 5s
      retries: 5

  backend:
    build:
      context: ./backend
      dockerfile: Dockerfile
    restart: always
    depends_on:
      db:
        condition: service_healthy
    environment:
      DATABASE_URL: postgresql+asyncpg://${DB_USER}:${DB_PASSWORD}@db:5432/centrum_operacyjne
    env_file:
      - ./backend/.env.production
    volumes:
      - uploads:/app/uploads
      - logs:/app/logs
    command: uvicorn src.api.main:app --host 0.0.0.0 --port 8000 --workers 1 --log-level warning
    logging:
      driver: "json-file"
      options:
        max-size: "10m"
        max-file: "5"

  caddy:
    image: caddy:2-alpine
    restart: always
    ports:
      - "80:80"
      - "443:443"
    volumes:
      - ./Caddyfile:/etc/caddy/Caddyfile
      - caddy_data:/data
      - caddy_config:/config
      - uploads:/app/uploads:ro
    depends_on:
      - backend

volumes:
  pgdata:
  uploads:
  logs:
  caddy_data:
  caddy_config:
```

**`backend/Dockerfile`** (nowy):

```dockerfile
FROM python:3.11-slim

WORKDIR /app

RUN apt-get update && apt-get install -y \
    gcc libpq-dev libxml2-dev libxslt1-dev \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY src/ src/
COPY data/ data/
COPY scripts/ scripts/

RUN mkdir -p uploads/reports logs

EXPOSE 8000

CMD ["uvicorn", "src.api.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "1"]
```

**`Caddyfile`**:

```
api.centrum-mieszkanca.pl {
    reverse_proxy backend:8000 {
        flush_interval -1  # SSE: wyłącz buforowanie
    }

    handle_path /uploads/* {
        file_server
        root * /app/uploads
    }

    header {
        X-Content-Type-Options nosniff
        X-Frame-Options DENY
        Referrer-Policy strict-origin-when-cross-origin
    }
}
```

---

## 7. Scenariusz Migracji Danych (Dev → Produkcja)

### Faza 1: Przygotowanie (Tydzień -1)

**Krok 1.1 - Audyt i rotacja sekretów**

Obecny `backend/.env` zawiera deweloperskie wartości. Stworzyć `.env.production`:

```bash
# Wygeneruj nowy JWT_SECRET (obecny to placeholder!)
openssl rand -hex 64

# Klucze API: przenieść z .env (te same klucze, nie zależą od środowiska)
# CORS_ORIGINS: zmienić na produkcyjną domenę
# APP_URL: zmienić na https://centrum-mieszkanca.pl
# DATABASE_URL: zmienić na produkcyjny connection string
```

Zmienne wymagające zmiany:
| Zmienna | Dev | Produkcja |
|---------|-----|-----------|
| `DATABASE_URL` | `localhost:5432` | `db:5432` (Docker) |
| `JWT_SECRET` | placeholder | `openssl rand -hex 64` |
| `CORS_ORIGINS` | `localhost:3001,...` | `https://centrum-mieszkanca.pl` |
| `APP_URL` | `http://localhost:3000` | `https://centrum-mieszkanca.pl` |
| `VAPID_CLAIMS_EMAIL` | ok | ok (już produkcyjna) |

**Krok 1.2 - Naprawy kodu przed deployem**

1. Zamiana Tailwind CDN na bundlowany build (index.html)
2. Weryfikacja czasu schedulera (resetować z 19:xx na 6:00-7:15)
3. Dodanie `stop_grace_period: 60s` w docker-compose (scheduler job AI trwa ~32 min)

### Faza 2: Infrastruktura (Dzień -3)

```bash
# 1. Zamów Hetzner CX22 (Falkenstein/Norymberga)
# 2. SSH do serwera
ssh root@<VPS_IP>

# 3. Podstawowa konfiguracja
apt update && apt upgrade -y
adduser deploy
usermod -aG sudo deploy

# 4. Zainstaluj Docker + Docker Compose
curl -fsSL https://get.docker.com | sh
usermod -aG docker deploy

# 5. Firewall
ufw allow 22/tcp   # SSH
ufw allow 80/tcp   # HTTP (redirect to HTTPS)
ufw allow 443/tcp  # HTTPS
ufw enable

# 6. Sklonuj repo
su - deploy
git clone https://github.com/<user>/Centrum_Operacyjne_Mieszkanca.git /opt/centrum
cd /opt/centrum
```

### Faza 3: Migracja Bazy Danych (Dzień -1)

```bash
# === NA MASZYNIE DEWELOPERSKIEJ ===

# 1. Eksport pełnego dumpa (format custom, kompresja)
pg_dump -Fc -h localhost -U user centrum_operacyjne \
  > centrum_backup_$(date +%Y%m%d).dump

# 2. Sprawdź rozmiar dumpa
ls -lh centrum_backup_*.dump
# Oczekiwany: ~50-100 MB

# 3. Transfer na VPS
scp centrum_backup_*.dump deploy@<VPS_IP>:/tmp/

# === NA VPS PRODUKCYJNYM ===

# 4. Uruchom bazę (tylko bazę, bez backendu)
cd /opt/centrum
docker compose -f docker-compose.prod.yml up -d db
sleep 10  # czekaj na startup PostgreSQL

# 5. Skopiuj dump do kontenera
docker cp /tmp/centrum_backup_*.dump centrum-db-1:/tmp/

# 6. Utwórz rozszerzenia PRZED importem
docker compose exec db psql -U $DB_USER -d centrum_operacyjne -c \
  "CREATE EXTENSION IF NOT EXISTS vector;
   CREATE EXTENSION IF NOT EXISTS pg_trgm;"

# 7. Import dumpa
docker compose exec db pg_restore -U $DB_USER \
  -d centrum_operacyjne \
  --no-owner --no-privileges \
  /tmp/centrum_backup_*.dump

# 8. Weryfikacja danych
docker compose exec db psql -U $DB_USER -d centrum_operacyjne -c "
  SELECT 'articles' as tbl, count(*) FROM articles
  UNION ALL SELECT 'document_embeddings', count(*) FROM document_embeddings
  UNION ALL SELECT 'users', count(*) FROM users
  UNION ALL SELECT 'waste_schedule', count(*) FROM waste_schedule
  UNION ALL SELECT 'sources', count(*) FROM sources;
"

# Oczekiwany wynik:
# articles            | ~1200
# document_embeddings |  ~170
# users               |  ~N
# waste_schedule      |  2663
# sources             |  ~10
```

### Faza 4: Migracja Plików (Dzień -1)

```bash
# Upload reportów (obecnie ~39 MB)
scp -r backend/uploads/reports/ deploy@<VPS_IP>:/opt/centrum/backend/uploads/reports/

# Cache danych (cinema, etc.)
scp -r backend/data/cache/ deploy@<VPS_IP>:/opt/centrum/backend/data/cache/
```

### Faza 5: Deploy Aplikacji (Dzień 0)

```bash
# === NA VPS ===

# 1. Skopiuj .env.production
scp backend/.env.production deploy@<VPS_IP>:/opt/centrum/backend/.env.production

# 2. Uruchom cały stack
cd /opt/centrum
docker compose -f docker-compose.prod.yml up -d

# 3. Uruchom migracje (idempotentne - bezpieczne do wielokrotnego uruchomienia)
docker compose exec backend python -m scripts.migrations.add_pgvector
docker compose exec backend python -m scripts.migrations.add_gus_database_first_tables
docker compose exec backend python -m scripts.migrations.add_push_subscriptions
docker compose exec backend python -m scripts.migrations.add_waste_schedule
docker compose exec backend python -m scripts.migrations.add_health_tables
docker compose exec backend python -m scripts.migrations.add_tsvector_bm25
docker compose exec backend python -m scripts.migrations.add_event_unique_constraint
docker compose exec backend python -m scripts.migrations.add_anonymous_chat_usage
docker compose exec backend python -m scripts.migrations.add_local_places

# 4. Test zdrowia
curl https://api.centrum-mieszkanca.pl/health
# {"status": "ok"}

# 5. Test endpointów
curl https://api.centrum-mieszkanca.pl/api/articles | head -c 200
curl https://api.centrum-mieszkanca.pl/api/weather
curl https://api.centrum-mieszkanca.pl/api/chat/agents
```

### Faza 6: Deploy Frontendu (Dzień 0)

```bash
# Opcja A: Via Cloudflare Pages (GitHub integration)
# Push do main → auto-deploy

# Opcja B: Manualny deploy via wrangler
cd frontend
VITE_API_URL=https://api.centrum-mieszkanca.pl/api npm run build
npx wrangler pages deploy dist/ --project-name centrum-mieszkanca
```

### Faza 7: DNS Cutover (Dzień 0)

1. W panelu Cloudflare DNS dodaj rekordy:
   - `A api → <IP_VPS>` (DNS only, szara chmurka)
   - `CNAME @ → centrum-mieszkanca.pages.dev` (Proxied)
   - `CNAME www → centrum-mieszkanca.pages.dev` (Proxied)
2. TTL: 300 sekund na czas cutoveru
3. Poczekaj na propagację DNS (~5-30 min)
4. Po stabilizacji: TTL → 3600 sekund

### Faza 8: Weryfikacja (Dzień 0+1)

- [ ] Frontend ładuje się pod `https://centrum-mieszkanca.pl`
- [ ] API odpowiada pod `https://api.centrum-mieszkanca.pl/health`
- [ ] Chat SSE działa (pytanie do agenta AI)
- [ ] Push notifications docierają
- [ ] PWA instaluje się na telefonie
- [ ] Scheduler uruchomił joby (sprawdź logi: `docker compose logs -f backend | grep scheduler`)
- [ ] Daily summary wygenerował się o 7:00
- [ ] Artykuły się scrapują o 6:00

---

## 8. Monitoring i Utrzymanie

### Uptime Monitoring (darmowy)

**UptimeRobot** (free tier, 50 monitorów, 5 min interwał):
- Monitor 1: `GET https://api.centrum-mieszkanca.pl/health` → expect `{"status": "ok"}`
- Monitor 2: `GET https://centrum-mieszkanca.pl` → expect HTTP 200
- Alert: email + opcjonalnie Telegram bot

### Logi

```bash
# Podgląd logów backendu
docker compose -f docker-compose.prod.yml logs -f backend --tail 100

# Logi schedulera (wewnątrz kontenera)
docker compose exec backend cat logs/scheduler.log | tail -50
```

### Automatyczny backup (cron na VPS)

```bash
# /etc/cron.d/centrum-backup
0 4 * * * deploy docker compose -f /opt/centrum/docker-compose.prod.yml exec -T db \
  pg_dump -Fc -U postgres centrum_operacyjne > /backups/centrum_$(date +\%Y\%m\%d).dump

0 5 * * * deploy find /backups/ -name "centrum_*.dump" -mtime +14 -delete

0 3 * * 0 deploy rclone copy /backups/ storagebox:centrum/ --max-age 7d
```

### Koszty AI API (estymacja)

| Usługa | Użycie/miesiąc | Koszt/mies. |
|--------|---------------|-------------|
| OpenAI GPT-4o-mini (routing) | ~3000 wywołań | ~2-3 USD |
| OpenAI GPT-4o (chat, summary) | ~1500 wywołań | ~5-8 USD |
| OpenAI embeddings | ~3000 artykułów | ~0.50 USD |
| Google Gemini (traffic) | ~184 wywołań | ~1-2 USD |
| Airly / OpenWeather | - | darmowy tier |
| Resend (email) | ~100 newsletterów/tydzień | darmowy tier |
| **RAZEM AI** | | **~10-15 USD/mies.** |

**Limit kosztów**: Ustaw w panelu OpenAI limit miesięczny 25 USD.

---

## 9. CI/CD Pipeline (GitHub Actions)

```yaml
# .github/workflows/deploy.yml
name: Deploy

on:
  push:
    branches: [main]

jobs:
  deploy-backend:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - name: Deploy via SSH
        uses: appleboy/ssh-action@v1
        with:
          host: ${{ secrets.VPS_HOST }}
          username: deploy
          key: ${{ secrets.SSH_PRIVATE_KEY }}
          script: |
            cd /opt/centrum
            git pull origin main
            docker compose -f docker-compose.prod.yml build backend
            docker compose -f docker-compose.prod.yml up -d backend
```

Frontend: automatyczny deploy przez Cloudflare Pages GitHub integration (push do main → build → deploy).

---

## 10. Checklist Bezpieczeństwa (PRZED deployem)

- [ ] Zrotować JWT_SECRET (obecny to placeholder)
- [ ] Zrotować klucze API jeśli były w historii Git
- [ ] `.env` w `.gitignore` (nie commitować sekretów)
- [ ] PostgreSQL credentials zmienione z `user:password`
- [ ] Adminer USUNIĘTY z docker-compose produkcyjnego
- [ ] CORS_ORIGINS ustawiony na produkcyjną domenę
- [ ] Firewall (ufw): tylko 22, 80, 443
- [ ] SSH: key-based auth, wyłączyć password login
- [ ] Port 5432 PostgreSQL NIE wystawiony na zewnątrz

---

## 11. Pliki do Stworzenia/Zmodyfikowania

| Plik | Akcja | Opis |
|------|-------|------|
| `docker-compose.prod.yml` | **NOWY** | Stack produkcyjny (db + backend + caddy) |
| `backend/Dockerfile` | **NOWY** | Obraz Docker dla FastAPI |
| `Caddyfile` | **NOWY** | Reverse proxy z auto-SSL |
| `backend/.env.production` | **NOWY** | Sekrety produkcyjne |
| `.github/workflows/deploy.yml` | **NOWY** | CI/CD pipeline |
| `frontend/index.html` | **EDYCJA** | Usunąć Tailwind CDN, importmap |
| `frontend/package.json` | **EDYCJA** | Dodać tailwindcss jako dev dep |
| `frontend/tailwind.config.js` | **NOWY** | Konfiguracja Tailwind build |
| `frontend/postcss.config.js` | **NOWY** | PostCSS z Tailwind plugin |
| `backend/src/config.py` | **EDYCJA** | Ew. domyślne wartości |
| `.dockerignore` | **NOWY** | Wykluczenia z Docker build |

---

## 12. Podsumowanie Kosztów

| | Budżetowy | Optymalny | Enterprise |
|--|-----------|-----------|------------|
| Infrastruktura | ~8 EUR | ~17 EUR | ~45 EUR |
| AI API | ~12 EUR | ~15 EUR | ~25 EUR |
| Domena | ~1 EUR | ~1 EUR | ~1 EUR |
| Frontend/CDN | 0 EUR | 0 EUR | 0 EUR |
| **MIESIĘCZNIE** | **~21 EUR** | **~33 EUR** | **~71 EUR** |
| **ROCZNIE** | **~252 EUR** | **~396 EUR** | **~852 EUR** |
