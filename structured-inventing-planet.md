# Plan Rozwoju: Premium Features & Monetyzacja Platformy
## Centrum Operacyjne Mieszkańca

**Data:** 2026-02-03
**Status:** Do zatwierdzenia
**Cel:** Zwiększenie atrakcyjności platformy poprzez wdrożenie funkcji Premium (19 zł/mc) i Business (99 zł/mc)

---

## Executive Summary

Plan wykorzystuje **strategię quick wins** - szybkie wdrożenie funkcji premium opartych na istniejącej infrastrukturze, następnie stopniowe dodawanie zaawansowanych funkcjonalności wymagających zewnętrznych integracji.

**Kluczowe założenia:**
- Wykorzystać dane które już mamy (GUS, artykuły, AI, weather)
- Priorytet dla funkcji o niskiej złożoności i wysokiej wartości
- Break-even: 18 użytkowników Premium LUB 4 użytkowników Business

**Roadmapa:**
- **Phase 1** (4 tyg): Quick Wins - podstawowe premium features → uzasadnienie 19 zł/mc
- **Phase 2** (8 tyg): Strategic Bets - integracje zewnętrzne (GIOŚ, Real Estate) → unique value
- **Phase 3** (12 tyg): Business Tier - API, raporty, analityka B2B → 99 zł/mc

---

## Stan Obecny MVP

### ✅ Mamy Już (Leverage Existing)

**Backend Infrastructure:**
- FastAPI + PostgreSQL + Redis
- APScheduler z 9 jobami (daily pipeline 6:00-8:00)
- OpenAI GPT-4o-mini (kategoryzacja) + GPT-4o (summaries)
- Resend (newsletter Weekly działa, Daily gotowy)
- JWT Auth z 3 tierami (free/premium/business)

**Dane:**
- **GUS API:** 25+ zmiennych (9 biznes, 4 demografia, 8 transport, 4 infrastruktura)
- **620+ artykułów** kategoryzowanych w 8 tematach
- **Weather** (OpenWeather API, refresh co 1h)
- **Daily Summaries** (AI-generated, 6:45 AM)
- **Traffic** (Gemini AI z Google Search grounding)
- **Cinema** (2 lokalizacje)

**Frontend:**
- React 19 + TypeScript + Vite + Tailwind
- GUSPage (5 wskaźników, wykresy Recharts)
- Dashboard z widgetami (AI summary, news, weather, traffic, cinema, bus)
- Auth flow (login, register, profile)
- 4 custom hooks (useArticles, useWeather, useEvents, useDailySummary)

**Database Schema:**
- 14 tabel (users, subscriptions, newsletter_subscribers, articles, events, weather, daily_summaries, gus_statistics, gus_gmina_stats, etc.)
- User.tier: free/premium/business
- NewsletterSubscriber.frequency: weekly/daily

---

## Strategia Monetyzacji

### Free Tier (0 zł)
- 5 podstawowych wskaźników GUS
- Chronologiczny feed artykułów (wszystkie kategorie)
- Newsletter tygodniowy (sobota 10:00)
- Obecny stan AQI (bez alertów)
- Reklamy displayowe (2-3 bannery)

### Premium Tier (19 zł/mc)
- ✅ **Daily Newsletter** (pon-pią 6:30) - już gotowy backend
- 📊 **Wszystkie 25+ wskaźniki GUS** + multi-metric porównanie
- 🔔 **Push Notifications** (personalizowane alerty)
- 📱 **10 SMS/mc** (critical alerts: smog, awarie)
- 🏷️ **Zaawansowane filtrowanie** artykułów (kategorie, tagi, lokalizacje)
- 💨 **Air Quality Monitoring** (GIOŚ API + trendy 30 dni)
- 🏠 **Real Estate Intelligence** (market summary, trend cen)
- 🚫 **Brak reklam**

### Business Tier (99 zł/mc)
- 🔑 **API Access** (1000 requests/day)
- 📊 **Eksport danych** (Excel, PDF)
- 📈 **Custom Reports** (GUS, nieruchomości, sentiment)
- 🎯 **Property Alerts** (zaniżone ceny, okazje)
- 📱 **50 SMS/mc**
- 🎨 **White-label** raporty

---

## Phase 1: Quick Wins (Tygodnie 1-4)

**Cel:** Uruchomić Premium za 19 zł z funkcjami które działają natychmiast

### 1.1. Daily Newsletter Automation (Tydzień 1)

**Status:** ✅ Backend GOTOWY (newsletter_daily job działa)

**Frontend Work:**
```typescript
// Plik: /frontend/src/pages/ProfilePage.tsx
// Linie 365-409 - rozbudowa istniejącego UI

interface NewsletterPreferences {
  weekly: boolean;
  daily: boolean;  // PREMIUM only
}

// Dodać handlery:
const handleNewsletterToggle = async (frequency: 'weekly' | 'daily', enabled: boolean) => {
  await fetch('/api/newsletter/preferences', {
    method: 'PUT',
    body: JSON.stringify({ frequency, enabled })
  });
};
```

**Backend Work:**
```python
# Plik: /backend/src/api/endpoints/newsletter.py (do utworzenia)

@router.put("/api/newsletter/preferences")
async def update_newsletter_preferences(
    frequency: str,
    enabled: bool,
    current_user: User = Depends(get_current_user)
):
    # Update NewsletterSubscriber.frequency
    # Jeśli daily && user.tier == "free" → HTTP 403
    pass
```

**Wartość:** "Zaoszczędź 15 minut rano - codzienne podsumowanie o 6:45"
**Koszty:** 0 PLN (Resend free tier: 3000 emails/mc)

---

### 1.2. Enhanced GUS Dashboard (Tydzień 2)

**Status:** ⚠️ GUSPage istnieje ale pokazuje tylko 5 zmiennych

**Frontend Enhancements:**
```typescript
// Plik: /frontend/src/pages/GUSPage.tsx
// Dodać 20+ nowych wskaźników z kategorii:

const PREMIUM_VARIABLES = {
  // Biznes (9 zmiennych)
  'sme_per_10k': { id: '1620132', name: 'MŚP na 10 tys.', tier: 'premium' },
  'large_entities_per_10k': { id: '634131', name: 'Duże firmy >49 osób', tier: 'premium' },
  'micro_enterprises_share': { id: '1548709', name: 'Udział mikrofirm %', tier: 'premium' },

  // Transport (8 zmiennych)
  'personal_cars': { id: '32561', name: 'Samochody osobowe', tier: 'premium' },
  'vehicles_per_1000': { id: '454131', name: 'Pojazdy na 1000 ludności', tier: 'premium' },

  // Infrastruktura (4 zmienne)
  'avg_salary': { id: '64428', name: 'Średnie wynagrodz. PLN', tier: 'business' },
};

// Premium paywall blur dla free users:
{!isPremium && (
  <div className="absolute inset-0 backdrop-blur-sm bg-white/60 flex items-center justify-center">
    <PremiumUpsellCard
      feature="Zaawansowane analizy GUS"
      benefits={["25+ wskaźników", "Multi-metric porównanie", "Export do Excel"]}
    />
  </div>
)}
```

**Backend Work:**
```python
# Plik: /backend/src/api/endpoints/stats.py
# Dodać nowe endpointy:

@router.get("/api/stats/multi-metric-comparison")
async def get_multi_metric_comparison(
    var_ids: List[str] = Query(...),
    current_user: User = Depends(require_premium)
):
    """Premium: Porównaj 2-5 wskaźników jednocześnie"""
    results = {}
    for var_id in var_ids:
        results[var_id] = await gus_service.get_comparative_stats(var_id)
    return results

@router.get("/api/stats/export")
async def export_gus_data(
    var_ids: List[str] = Query(...),
    format: str = "xlsx",  # xlsx, csv, pdf
    current_user: User = Depends(require_business)
):
    """Business: Export GUS data"""
    # Generate Excel/CSV using openpyxl or pandas
    pass
```

**Wartość:**
- Free: 5 podstawowych wskaźników (single view)
- Premium: 25+ wskaźników + multi-metric + trendy YoY
- Business: Export + API access

**Koszty:** 0 PLN (GUS API darmowe)

---

### 1.3. Article Filtering & Personalization (Tydzień 3)

**Status:** ✅ Artykuły mają `category`, `tags`, `location_mentioned`

**Frontend Work:**
```typescript
// Plik: /frontend/components/NewsFeed.tsx
// Dodać panel filtrowania:

const FilterSidebar = () => {
  const { user } = useAuth();
  const isPremium = user?.tier !== 'free';

  return (
    <div className="space-y-4">
      {/* Kategorie - dostępne dla wszystkich */}
      <FilterSection title="Kategorie">
        {CATEGORIES.map(cat => (
          <FilterCheckbox key={cat} label={cat} onChange={...} />
        ))}
      </FilterSection>

      {/* Tagi - PREMIUM */}
      <FilterSection
        title="Tagi"
        isPremium={true}
        locked={!isPremium}
      >
        {isPremium ? (
          <TagCloud tags={availableTags} onSelect={...} />
        ) : (
          <div className="blur-sm">
            <TagCloud tags={MOCK_TAGS} disabled />
          </div>
        )}
      </FilterSection>

      {/* Lokalizacje - PREMIUM */}
      <FilterSection
        title="Lokalizacje"
        isPremium={true}
        locked={!isPremium}
      >
        {/* Similar blur for free users */}
      </FilterSection>
    </div>
  );
};
```

**Backend Work:**
```python
# Plik: /backend/src/api/endpoints/articles.py
# Rozbudować istniejący endpoint:

@router.get("/api/articles/personalized")
async def get_personalized_feed(
    categories: Optional[List[str]] = Query(None),
    tags: Optional[List[str]] = Query(None),
    locations: Optional[List[str]] = Query(None),
    current_user: User = Depends(get_current_user_optional)
):
    query = select(Article)

    # Podstawowe filtrowanie po kategoriach - dla wszystkich
    if categories:
        query = query.where(Article.category.in_(categories))

    # Premium features
    if tags or locations:
        if not current_user or current_user.tier == "free":
            raise HTTPException(403, "Premium feature")

        if tags:
            query = query.where(Article.tags.overlap(tags))
        if locations:
            query = query.where(Article.location_mentioned.overlap(locations))

    return await db.execute(query)
```

**Wartość:**
- Free: Filtrowanie po kategoriach
- Premium: + tagi + lokalizacje + saved searches
- Business: + email alerts dla custom queries

**Koszty:** 0 PLN

---

### 1.4. Ad-Free Experience (Tydzień 4)

**Status:** ❌ Obecnie brak reklam w MVP

**Frontend Work:**
```typescript
// Plik: /frontend/components/AdBanner.tsx (nowy)

const AdBanner = ({ placement }: { placement: 'sidebar' | 'article' | 'feed' }) => {
  const { user } = useAuth();

  // Premium/Business users nie widzą reklam
  if (user?.tier !== 'free') return null;

  return (
    <div className="bg-slate-50 p-4 rounded-xl border border-slate-200">
      <p className="text-xs text-slate-400 mb-2">REKLAMA</p>
      <div className="bg-white p-6 min-h-[250px] flex items-center justify-center">
        {/* Google AdSense placeholder */}
        <ins className="adsbygoogle"
             style={{ display: 'block' }}
             data-ad-client="ca-pub-XXXXXXXX"
             data-ad-slot="1234567890"
             data-ad-format="auto" />
      </div>
      <button
        onClick={() => navigate('/premium')}
        className="text-xs text-blue-600 hover:underline mt-2"
      >
        🚫 Usuń reklamy - zostań Premium →
      </button>
    </div>
  );
};

// Użycie w Dashboard.tsx, NewsFeed.tsx:
<AdBanner placement="sidebar" />
```

**Monetyzacja:**
- Free: 2-3 bannery (AdSense: ~5-10 PLN/1000 wyświetleń)
- Przy 1000 użytkowników free × 50 wyświetleń/mc = ~250-500 PLN/mc

**Koszty:** 0 PLN (AdSense generuje przychód)

---

## Phase 2: Strategic Bets (Tygodnie 5-12)

**Cel:** Funkcje wymagające zewnętrznych integracji - unique value

### 2.1. GIOŚ Air Quality Monitoring (Tygodnie 5-6)

**Backend Work:**
```python
# Plik: /backend/src/integrations/gios_api.py (nowy)

class GIOSService:
    """Integracja z API GIOŚ - Główny Inspektorat Ochrony Środowiska"""
    BASE_URL = "https://api.gios.gov.pl/pjp-api/v1"

    # Znajdź ID stacji dla Działdowa:
    # https://api.gios.gov.pl/pjp-api/v1/station/findAll
    STATION_ID = "TODO"  # Sprawdzić dokumentację

    async def get_air_quality(self) -> dict:
        """
        Pobierz AQI (Air Quality Index)
        Returns: {
            "pm10": 45.2,
            "pm25": 32.1,
            "aqi_level": "GOOD",  # GOOD, MODERATE, BAD, VERY_BAD, HAZARDOUS
            "aqi_color": "#10b981",
            "advice": "Jakość powietrza dobra. Możesz wyjść na spacer."
        }
        """
        # GET /pjp-api/v1/aqindex/getIndex/{stationId}
        pass

# Plik: /backend/src/database/schema.py
# Dodać nową tabelę:

class AirQuality(SQLModel, table=True):
    __tablename__ = "air_quality"

    id: Optional[int] = Field(default=None, primary_key=True)
    location: str = Field(default="Działdowo", index=True)
    pm10: Optional[float] = None
    pm25: Optional[float] = None
    aqi_level: str  # GOOD, MODERATE, BAD, VERY_BAD, HAZARDOUS
    aqi_index: int  # 0-500
    measured_at: datetime = Field(index=True)
    fetched_at: datetime = Field(default_factory=datetime.utcnow)

# Plik: /backend/src/scheduler/jobs/air_quality_job.py (nowy)
# Dodać job do schedulera (refresh co 1h):

async def update_air_quality():
    gios = GIOSService()
    data = await gios.get_air_quality()

    # Zapisz do bazy
    air_quality = AirQuality(**data)
    db.add(air_quality)

    # Sprawdź czy wysłać alerty (PM2.5 > 50)
    if data['pm25'] and data['pm25'] > 50:
        await send_premium_alerts(
            title="⚠️ Smog Alert",
            message=f"PM2.5: {data['pm25']} µg/m³. Ogranicz aktywność na zewnątrz."
        )
```

**Frontend Work:**
```typescript
// Plik: /frontend/components/widgets/AirQualityWidget.tsx (nowy)

const AirQualityWidget = () => {
  const { data, isLoading } = useAirQuality();
  const { user } = useAuth();
  const isPremium = user?.tier !== 'free';

  const getAQIColor = (level: string) => {
    const colors = {
      'GOOD': 'bg-green-500',
      'MODERATE': 'bg-yellow-500',
      'BAD': 'bg-orange-500',
      'VERY_BAD': 'bg-red-500',
      'HAZARDOUS': 'bg-purple-600'
    };
    return colors[level] || 'bg-slate-500';
  };

  return (
    <div className={`p-6 rounded-2xl text-white ${getAQIColor(data.aqi_level)}`}>
      <div className="flex items-center justify-between mb-4">
        <h3 className="font-bold text-lg">💨 Jakość Powietrza</h3>
        <span className="text-sm opacity-80">
          {new Date(data.measured_at).toLocaleTimeString('pl-PL')}
        </span>
      </div>

      <div className="text-5xl font-black mb-2">{data.aqi_level}</div>

      <div className="space-y-1 text-sm opacity-90">
        <p>PM2.5: {data.pm25} µg/m³</p>
        <p>PM10: {data.pm10} µg/m³</p>
      </div>

      <p className="text-sm mt-4 opacity-80">{data.advice}</p>

      {!isPremium && (
        <button
          onClick={() => navigate('/premium')}
          className="mt-4 w-full bg-white/20 hover:bg-white/30 px-4 py-2 rounded-xl text-sm font-medium transition-colors"
        >
          🔔 Premium: SMS alerty przy złym powietrzu →
        </button>
      )}
    </div>
  );
};

// Dodać do Dashboard.tsx
```

**API Endpoint:**
```python
# /backend/src/api/endpoints/air_quality.py (nowy)

@router.get("/api/air-quality")
async def get_air_quality():
    """Obecny stan jakości powietrza - publiczny"""
    return await db.execute(
        select(AirQuality)
        .order_by(AirQuality.measured_at.desc())
        .limit(1)
    )

@router.get("/api/air-quality/trend")
async def get_air_quality_trend(
    days: int = 30,
    current_user: User = Depends(require_premium)
):
    """Premium: Trend ostatnich 30 dni"""
    return await db.execute(
        select(AirQuality)
        .where(AirQuality.measured_at >= datetime.now() - timedelta(days=days))
        .order_by(AirQuality.measured_at)
    )
```

**Wartość:**
- Free: Obecny AQI (refresh co 1h)
- Premium: Trendy 30 dni + Push/SMS alerty przy PM2.5 > 50
- Business: API access + eksport danych

**Koszty:**
- GIOŚ API: FREE
- SMS: ~0.10 PLN/SMS × max 5 alertów/mc = 50 PLN/100 users

---

### 2.2. Real Estate Market Intelligence (Tygodnie 7-9)

**Backend Work:**
```python
# Plik: /backend/src/scrapers/real_estate_scraper.py (nowy)

class RealEstateScraper(BaseScraper):
    """Scraper dla OLX i Otodom - ogłoszenia nieruchomości"""

    async def scrape_olx(self, location: str = "Działdowo"):
        """
        Scrape OLX property listings
        Returns: [{
            "title": "Mieszkanie 50m² Centrum Działdowo",
            "price": 280000,
            "price_per_sqm": 5600,
            "sqm": 50,
            "location": "Działdowo, ul. Norwida",
            "rooms": 3,
            "floor": 2,
            "url": "https://olx.pl/..."
        }]
        """
        # BeautifulSoup parsing
        pass

    async def scrape_otodom(self, location: str = "Działdowo"):
        """Similar for Otodom"""
        pass

# Plik: /backend/src/database/schema.py
# Dodać tabelę:

class RealEstateListing(SQLModel, table=True):
    __tablename__ = "real_estate_listings"

    id: Optional[int] = Field(default=None, primary_key=True)
    source: str = Field(index=True)  # "olx", "otodom"
    external_id: str = Field(unique=True)
    title: str
    price: int
    price_per_sqm: Optional[float] = None
    sqm: Optional[float] = None
    rooms: Optional[int] = None
    floor: Optional[int] = None
    location: str = Field(index=True)
    neighborhood: Optional[str] = None  # "Centrum", "Osiedle Nidzicka"
    url: str
    image_url: Optional[str] = None
    published_date: Optional[datetime] = None
    scraped_at: datetime = Field(default_factory=datetime.utcnow)
    is_active: bool = Field(default=True)

# Plik: /backend/src/scheduler/jobs/real_estate_job.py (nowy)
# Scraping codziennie o 7:00

async def scrape_real_estate():
    scraper = RealEstateScraper()
    listings = await scraper.scrape_all()

    for listing in listings:
        # Deduplication
        existing = await db.execute(
            select(RealEstateListing)
            .where(RealEstateListing.external_id == listing['external_id'])
        )

        if not existing:
            db.add(RealEstateListing(**listing))

            # Sprawdź czy to "okazja" (price_per_sqm < avg - 15%)
            avg_price = await calculate_avg_price_per_sqm(listing['neighborhood'])
            if listing['price_per_sqm'] < avg_price * 0.85:
                await send_business_alert(
                    title="🏠 Underpriced Property Alert",
                    listing=listing
                )
```

**Backend API:**
```python
# /backend/src/api/endpoints/real_estate.py (nowy)

@router.get("/api/real-estate/market-summary")
async def get_market_summary(
    current_user: User = Depends(require_premium)
):
    """
    Premium: Market summary
    Returns: {
        "total_listings": 47,
        "avg_price_per_sqm": 5243,
        "trend_30d": -2.3,  # % change
        "neighborhoods": {
            "Centrum": {
                "avg_price_sqm": 5800,
                "listings_count": 12,
                "trend": 1.5
            },
            "Osiedle Nidzicka": {
                "avg_price_sqm": 4900,
                "listings_count": 18,
                "trend": -3.2
            }
        }
    }
    """
    pass

@router.get("/api/real-estate/listings")
async def get_listings(
    limit: int = 50,
    neighborhood: Optional[str] = None,
    current_user: User = Depends(require_premium)
):
    """Premium: All listings"""
    pass

@router.get("/api/real-estate/deals")
async def get_underpriced_deals(
    current_user: User = Depends(require_business)
):
    """Business: Underpriced properties (okazje)"""
    # price_per_sqm < avg - 15%
    pass
```

**Frontend Work:**
```typescript
// Plik: /frontend/src/pages/RealEstatePage.tsx (nowy)

const RealEstatePage = () => {
  const { marketSummary, listings, isLoading } = useRealEstate();
  const { user } = useAuth();

  if (!user || user.tier === 'free') {
    return <PremiumPaywall feature="Real Estate Intelligence" />;
  }

  return (
    <div className="space-y-8">
      <h1 className="text-3xl font-black">🏠 Rynek Nieruchomości</h1>

      {/* Market Summary Cards */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
        <StatCard
          title="Średnia cena/m²"
          value={`${marketSummary.avg_price_per_sqm.toLocaleString()} PLN`}
          trend={marketSummary.trend_30d}
        />
        <StatCard
          title="Aktywne ogłoszenia"
          value={marketSummary.total_listings}
        />
        <StatCard
          title="Najdroższe osiedle"
          value="Centrum"
          subtitle="5,800 PLN/m²"
        />
      </div>

      {/* Neighborhood Heatmap */}
      <div className="bg-white rounded-2xl p-8">
        <h3 className="font-bold mb-4">Mapa cieplna - ceny po osiedlach</h3>
        <NeighborhoodHeatmap data={marketSummary.neighborhoods} />
      </div>

      {/* Listings Table */}
      <div className="bg-white rounded-2xl p-8">
        <h3 className="font-bold mb-4">Najnowsze ogłoszenia</h3>
        <ListingsTable listings={listings} />
      </div>

      {/* Business Tier Upsell */}
      {user.tier !== 'business' && (
        <div className="bg-gradient-to-r from-slate-800 to-slate-900 text-white rounded-2xl p-8">
          <h3 className="text-xl font-bold mb-2">🎯 Upgrade to Business</h3>
          <p className="mb-4">Get instant alerts for underpriced properties</p>
          <button className="bg-white text-slate-900 px-6 py-2 rounded-xl font-bold">
            Learn More →
          </button>
        </div>
      )}
    </div>
  );
};
```

**Wartość:**
- Free: Brak dostępu
- Premium: Market summary + wszystkie ogłoszenia + trend 30 dni
- Business: + Alerty o okazjach + ROI calculator

**Koszty:**
- Scraping: 0 PLN (własny scraper) LUB ~30 PLN/mc (Apify actor)

---

### 2.3. Push Notifications (Tygodnie 10-11)

**Backend Work:**
```python
# Plik: /backend/src/notifications/push_service.py (nowy)

from pywebpush import webpush
import json

class PushNotificationService:
    """Web Push using VAPID protocol (self-hosted, FREE)"""

    def __init__(self):
        self.vapid_private_key = settings.VAPID_PRIVATE_KEY
        self.vapid_public_key = settings.VAPID_PUBLIC_KEY
        self.vapid_claims = {"sub": "mailto:kontakt@dzialdowolive.pl"}

    async def send_push(
        self,
        subscription_info: dict,
        title: str,
        message: str,
        url: Optional[str] = None
    ):
        """
        Wyślij push notification
        subscription_info: {
            "endpoint": "https://...",
            "keys": {"p256dh": "...", "auth": "..."}
        }
        """
        try:
            webpush(
                subscription_info=subscription_info,
                data=json.dumps({
                    "title": title,
                    "body": message,
                    "icon": "/logo192.png",
                    "url": url or "/"
                }),
                vapid_private_key=self.vapid_private_key,
                vapid_claims=self.vapid_claims
            )
            logger.info(f"Push sent: {title}")
        except Exception as e:
            logger.error(f"Push failed: {e}")

# Plik: /backend/src/database/schema.py
# Dodać tabelę:

class PushSubscription(SQLModel, table=True):
    __tablename__ = "push_subscriptions"

    id: Optional[int] = Field(default=None, primary_key=True)
    user_id: int = Field(foreign_key="users.id", index=True)
    endpoint: str = Field(unique=True)
    p256dh_key: str
    auth_key: str
    user_agent: Optional[str] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)
    last_used: Optional[datetime] = None

# Plik: /backend/src/api/endpoints/notifications.py (nowy)

@router.post("/api/notifications/subscribe")
async def subscribe_to_push(
    subscription: dict,
    current_user: User = Depends(require_premium)
):
    """Premium: Subscribe to push notifications"""
    push_sub = PushSubscription(
        user_id=current_user.id,
        endpoint=subscription['endpoint'],
        p256dh_key=subscription['keys']['p256dh'],
        auth_key=subscription['keys']['auth']
    )
    db.add(push_sub)
    return {"status": "subscribed"}

@router.post("/api/notifications/test")
async def test_push(current_user: User = Depends(require_premium)):
    """Test push notification"""
    await push_service.send_push(
        subscription_info=current_user.push_subscription,
        title="Test Push",
        message="To jest test powiadomienia push!"
    )
```

**Frontend Work:**
```typescript
// Plik: /frontend/src/services/pushNotifications.ts (nowy)

const VAPID_PUBLIC_KEY = import.meta.env.VITE_VAPID_PUBLIC_KEY;

export const subscribeToPush = async () => {
  // Sprawdź wsparcie przeglądarki
  if (!('Notification' in window)) {
    throw new Error('Przeglądarka nie wspiera powiadomień');
  }

  // Request permission
  const permission = await Notification.requestPermission();
  if (permission !== 'granted') {
    throw new Error('Brak zgody na powiadomienia');
  }

  // Register service worker
  const registration = await navigator.serviceWorker.register('/sw.js');

  // Subscribe to push
  const subscription = await registration.pushManager.subscribe({
    userVisibleOnly: true,
    applicationServerKey: urlBase64ToUint8Array(VAPID_PUBLIC_KEY)
  });

  // Wyślij subscription do backendu
  await fetch('/api/notifications/subscribe', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(subscription)
  });

  return subscription;
};

// Plik: /frontend/public/sw.js (service worker)

self.addEventListener('push', (event) => {
  const data = event.data.json();

  self.registration.showNotification(data.title, {
    body: data.body,
    icon: data.icon || '/logo192.png',
    badge: '/badge.png',
    data: { url: data.url }
  });
});

self.addEventListener('notificationclick', (event) => {
  event.notification.close();
  event.waitUntil(
    clients.openWindow(event.notification.data.url)
  );
});

// Plik: /frontend/src/pages/ProfilePage.tsx
// Dodać przycisk w zakładce "Preferencje":

<button
  onClick={subscribeToPush}
  className="px-4 py-2 bg-blue-600 text-white rounded-xl"
>
  🔔 Włącz powiadomienia Push
</button>
```

**Push Triggers (automatyczne):**
1. Nowy artykuł w preferowanych kategoriach
2. Smog alert (PM2.5 > 50)
3. Korek na trasie (>15 min delay)
4. Nowe ogłoszenie nieruchomości (underpriced)
5. Awaria prądu/wody w okolicy

**Wartość:**
- Free: Brak push
- Premium: Unlimited push + customizable triggers
- Business: + Webhooks API

**Koszty:** 0 PLN (Web Push via VAPID - self-hosted, FREE)

---

### 2.4. SMS Alerts (Tydzień 12)

**Backend Work:**
```python
# Plik: /backend/src/notifications/sms_service.py (nowy)

import aiohttp

class SMSService:
    """SMS via SMSAPI.pl"""
    BASE_URL = "https://api.smsapi.pl"

    def __init__(self):
        self.token = settings.SMSAPI_TOKEN
        self.sender_name = "DzialdowoLV"  # Zarejestrowana nazwa

    async def send_sms(self, phone: str, message: str):
        """
        Wyślij SMS
        phone: "+48123456789"
        message: max 160 znaków
        """
        async with aiohttp.ClientSession() as session:
            async with session.post(
                f"{self.BASE_URL}/sms.do",
                headers={"Authorization": f"Bearer {self.token}"},
                json={
                    "to": phone,
                    "message": message,
                    "from": self.sender_name,
                    "format": "json"
                }
            ) as response:
                result = await response.json()
                logger.info(f"SMS sent to {phone}: {result}")
                return result

# Dodać do User schema:

class User(SQLModel, table=True):
    # ... existing fields
    phone: Optional[str] = None  # NOWE pole
    sms_quota_used: int = Field(default=0)  # Counter dla Premium (max 10/mc)
    sms_quota_reset_at: Optional[datetime] = None

# SMS Triggers (tylko critical alerts):

async def send_critical_sms_alert(alert_type: str, details: dict):
    """Wysyła SMS do Premium users przy krytycznych alertach"""

    # 1. Smog Critical (PM2.5 > 100)
    if alert_type == "smog_critical":
        message = f"⚠️ SMOG! PM2.5: {details['pm25']}. Zostań w domu."

    # 2. Water Contamination
    elif alert_type == "water_contamination":
        message = "⚠️ WODA NIEZDATNA! Beczki przy Rynku."

    # 3. Severe Weather (wichura >90 km/h)
    elif alert_type == "severe_weather":
        message = f"⚠️ Wichura {details['wind_speed']} km/h. Unikaj wyjścia."

    # Pobierz Premium users z phone
    premium_users = await db.execute(
        select(User)
        .where(User.tier.in_(["premium", "business"]))
        .where(User.phone.isnot(None))
        .where(User.sms_quota_used < get_sms_limit(User.tier))
    )

    for user in premium_users:
        await sms_service.send_sms(user.phone, message)
        user.sms_quota_used += 1
        await db.commit()
```

**Frontend Work:**
```typescript
// Plik: /frontend/src/pages/ProfilePage.tsx
// Dodać pole telefonu w zakładce Profile:

<div>
  <label className="block text-sm font-semibold text-slate-700 mb-2">
    Numer telefonu
    {user.tier !== 'free' && (
      <span className="ml-2 text-xs bg-blue-100 text-blue-600 px-2 py-0.5 rounded">
        Premium
      </span>
    )}
  </label>
  <input
    type="tel"
    value={profileData.phone}
    onChange={(e) => setProfileData(p => ({ ...p, phone: e.target.value }))}
    placeholder="+48 123 456 789"
    disabled={user.tier === 'free'}
    className="w-full px-4 py-3 rounded-xl border border-slate-200"
  />
  <p className="text-xs text-slate-400 mt-1">
    {user.tier !== 'free'
      ? `Otrzymasz SMS przy krytycznych alertach (${user.sms_quota_used}/10 w tym miesiącu)`
      : 'Alerty SMS dostępne w planie Premium'
    }
  </p>
</div>
```

**Wartość:**
- Free: Brak SMS
- Premium: 10 SMS/mc (tylko critical)
- Business: 50 SMS/mc

**Koszty:**
- SMSAPI: ~0.10 PLN/SMS
- Premium: max 10 SMS/user × 50 users = 500 SMS × 0.10 = **50 PLN/mc**
- Business: max 50 SMS/user × 10 users = 500 SMS × 0.10 = **50 PLN/mc**
- **TOTAL SMS cost: ~100 PLN/mc**

---

## Phase 3: Business Tier (Tygodnie 13-24)

**Cel:** Monetyzacja B2B - API, raporty, analityka

### 3.1. Public API (Tygodnie 13-16)

**Backend Work:**
```python
# Plik: /backend/src/database/schema.py
# Dodać tabelę:

class APIKey(SQLModel, table=True):
    __tablename__ = "api_keys"

    id: Optional[int] = Field(default=None, primary_key=True)
    user_id: int = Field(foreign_key="users.id", index=True)
    key: str = Field(unique=True, index=True)  # UUID
    name: str  # "Production API", "Test API"
    rate_limit_day: int = Field(default=1000)
    requests_today: int = Field(default=0)
    last_used: Optional[datetime] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)
    revoked_at: Optional[datetime] = None

# Plik: /backend/src/api/v1/business_api.py (nowy)

from fastapi import Header

async def verify_api_key(x_api_key: str = Header(...)):
    """Middleware dla Business API"""
    api_key = await db.execute(
        select(APIKey)
        .where(APIKey.key == x_api_key)
        .where(APIKey.revoked_at.is_(None))
    )

    if not api_key:
        raise HTTPException(401, "Invalid API key")

    # Sprawdź rate limit
    if api_key.requests_today >= api_key.rate_limit_day:
        raise HTTPException(429, "Rate limit exceeded")

    # Increment counter
    api_key.requests_today += 1
    api_key.last_used = datetime.utcnow()
    await db.commit()

    return api_key

# Endpoints:

@router.get("/api/v1/articles")
async def get_articles_api(
    category: Optional[str] = None,
    limit: int = 50,
    api_key: APIKey = Depends(verify_api_key)
):
    """Business API: Get articles"""
    pass

@router.get("/api/v1/stats/gus")
async def get_gus_stats_api(
    var_id: str,
    api_key: APIKey = Depends(verify_api_key)
):
    """Business API: GUS statistics"""
    pass

@router.post("/api/v1/webhooks")
async def create_webhook(
    url: str,
    events: List[str],  # ["new_article", "smog_alert", "property_alert"]
    api_key: APIKey = Depends(verify_api_key)
):
    """Business: Register webhook"""
    pass
```

**Frontend Work:**
```typescript
// Plik: /frontend/src/pages/DeveloperPage.tsx (nowy)

const DeveloperPage = () => {
  const { user } = useAuth();
  const [apiKeys, setApiKeys] = useState([]);

  if (user?.tier !== 'business') {
    return <BusinessPaywall />;
  }

  const generateAPIKey = async () => {
    const response = await fetch('/api/api-keys', {
      method: 'POST',
      body: JSON.stringify({ name: 'My API Key' })
    });
    const key = await response.json();
    setApiKeys([...apiKeys, key]);
  };

  return (
    <div>
      <h1 className="text-3xl font-black mb-8">🔑 Developer API</h1>

      <div className="bg-white rounded-2xl p-8 mb-6">
        <h3 className="font-bold mb-4">Your API Keys</h3>
        <button onClick={generateAPIKey} className="px-4 py-2 bg-blue-600 text-white rounded-xl">
          + Generate New Key
        </button>

        <div className="mt-6 space-y-4">
          {apiKeys.map(key => (
            <div key={key.id} className="p-4 bg-slate-50 rounded-xl font-mono text-sm">
              <div className="flex justify-between items-center">
                <code>{key.key}</code>
                <span className="text-xs text-slate-400">
                  {key.requests_today}/1000 today
                </span>
              </div>
            </div>
          ))}
        </div>
      </div>

      <div className="bg-white rounded-2xl p-8">
        <h3 className="font-bold mb-4">📚 API Documentation</h3>
        <pre className="bg-slate-900 text-green-400 p-4 rounded-xl overflow-x-auto">
{`curl -X GET 'https://api.dzialdowolive.pl/v1/articles' \\
  -H 'X-API-Key: your-api-key-here'`}
        </pre>

        <a href="/docs" className="text-blue-600 hover:underline mt-4 inline-block">
          View Full API Docs (Swagger) →
        </a>
      </div>
    </div>
  );
};
```

**Wartość:**
- 1000 requests/day
- Webhooks support
- Full Swagger docs
- Rate limiting

**Koszty:** 0 PLN

---

### 3.2. Custom Reports & Export (Tygodnie 17-19)

**Backend Work:**
```python
# Plik: /backend/src/reports/generator.py (nowy)

from openpyxl import Workbook
from openpyxl.chart import LineChart, Reference
from io import BytesIO

class ReportGenerator:
    """Generator raportów Excel/PDF dla Business tier"""

    async def generate_market_report(
        self,
        format: str = "xlsx",
        date_from: datetime = None,
        date_to: datetime = None
    ) -> bytes:
        """
        Generuj raport rynkowy
        Zawiera:
        - GUS statistics trends (25 lat)
        - Real estate market summary
        - News sentiment analysis
        - Weather trends
        """
        if format == "xlsx":
            return await self._generate_excel_report(date_from, date_to)
        elif format == "pdf":
            return await self._generate_pdf_report(date_from, date_to)

    async def _generate_excel_report(self, date_from, date_to) -> bytes:
        wb = Workbook()

        # Sheet 1: GUS Statistics
        ws1 = wb.active
        ws1.title = "GUS Statistics"
        ws1['A1'] = "Rok"
        ws1['B1'] = "Podmioty REGON/10k"
        ws1['C1'] = "Bezrobocie %"

        # Populate data from gus_gmina_stats
        gus_data = await db.execute(
            select(GUSGminaStats)
            .where(GUSGminaStats.unit_id == "042815403062")
            .order_by(GUSGminaStats.year)
        )

        row = 2
        for record in gus_data:
            ws1[f'A{row}'] = record.year
            ws1[f'B{row}'] = record.value
            row += 1

        # Add chart
        chart = LineChart()
        chart.title = "Trend Przedsiębiorczości"
        data = Reference(ws1, min_col=2, min_row=1, max_row=row-1)
        cats = Reference(ws1, min_col=1, min_row=2, max_row=row-1)
        chart.add_data(data, titles_from_data=True)
        chart.set_categories(cats)
        ws1.add_chart(chart, "E5")

        # Sheet 2: Real Estate
        ws2 = wb.create_sheet("Real Estate")
        ws2['A1'] = "Osiedle"
        ws2['B1'] = "Średnia cena/m²"
        ws2['C1'] = "Liczba ogłoszeń"

        # ... populate real estate data

        # Save to BytesIO
        stream = BytesIO()
        wb.save(stream)
        stream.seek(0)
        return stream.getvalue()

# API Endpoint:

@router.get("/api/reports/market")
async def generate_market_report(
    format: str = "xlsx",
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
    current_user: User = Depends(require_business)
):
    """Business: Generate custom market report"""
    generator = ReportGenerator()
    report_bytes = await generator.generate_market_report(format, date_from, date_to)

    filename = f"market_report_{datetime.now().strftime('%Y%m%d')}.{format}"

    return Response(
        content=report_bytes,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f"attachment; filename={filename}"}
    )
```

**Frontend Work:**
```typescript
// Plik: /frontend/src/pages/ReportsPage.tsx (nowy)

const ReportsPage = () => {
  const { user } = useAuth();

  const downloadReport = async (reportType: string, format: string) => {
    const response = await fetch(`/api/reports/${reportType}?format=${format}`, {
      headers: { 'Authorization': `Bearer ${token}` }
    });

    const blob = await response.blob();
    const url = window.URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `${reportType}_${new Date().toISOString()}.${format}`;
    a.click();
  };

  return (
    <div>
      <h1 className="text-3xl font-black mb-8">📊 Raporty</h1>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
        <ReportCard
          title="Raport Rynkowy"
          description="GUS + Nieruchomości + Sentiment"
          onDownload={() => downloadReport('market', 'xlsx')}
          formats={['xlsx', 'pdf']}
        />

        <ReportCard
          title="Analiza Trendów"
          description="Trendy 25 lat GUS"
          onDownload={() => downloadReport('trends', 'xlsx')}
          formats={['xlsx', 'csv']}
        />
      </div>
    </div>
  );
};
```

**Wartość:**
- Automated reports (Excel, PDF, CSV)
- 25 lat danych historycznych GUS
- White-label (logo firmy)
- Scheduled reports (email co tydzień)

**Koszty:** 0 PLN (openpyxl/reportlab free)

---

### 3.3. Utility Alerts (Tygodnie 20-22)

**Backend Work:**
```python
# Plik: /backend/src/scrapers/utility_scraper.py (nowy)

class UtilityScraper:
    """Scraper dla awarii mediów (Energa, Wodociągi)"""

    async def scrape_energa_outages(self):
        """
        Scrape energa-operator.pl/brak-pradu
        Returns: [{
            "type": "power",
            "status": "planned",
            "start_time": "2026-02-05 08:00",
            "end_time": "2026-02-05 14:00",
            "affected_streets": ["ul. Norwida", "ul. Piłsudskiego"],
            "affected_addresses": ["1-25", "26-50"],
            "reason": "Modernizacja sieci SN"
        }]
        """
        pass

# Plik: /backend/src/database/schema.py

class UtilityOutage(SQLModel, table=True):
    __tablename__ = "utility_outages"

    id: Optional[int] = Field(default=None, primary_key=True)
    utility_type: str = Field(index=True)  # "power", "water", "gas"
    status: str  # "planned", "unplanned"
    start_time: datetime = Field(index=True)
    end_time: Optional[datetime] = None
    affected_streets: List[str] = Field(sa_column=Column(ARRAY(String)))
    reason: Optional[str] = None
    source_url: Optional[str] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)
    resolved_at: Optional[datetime] = None

# Alert Logic:

async def check_user_affected(outage: UtilityOutage, user: User) -> bool:
    """Sprawdź czy user jest dotknięty awarią"""
    # Parse user.location: "Działdowo, ul. Norwida 15"
    user_street = extract_street(user.location)
    return user_street in outage.affected_streets

async def send_utility_alerts(outage: UtilityOutage):
    """Wyślij alerty o awarii"""

    # 24h przed planowaną awarią - Push
    if outage.status == "planned":
        time_until = outage.start_time - datetime.now()
        if timedelta(hours=23) < time_until < timedelta(hours=25):
            await send_push_to_affected_users(
                outage,
                title=f"⚠️ Planowana awaria {outage.utility_type}",
                message=f"Jutro {outage.start_time.strftime('%H:%M')}-{outage.end_time.strftime('%H:%M')}"
            )

    # 1h przed - SMS (tylko Premium)
    if timedelta(minutes=55) < time_until < timedelta(hours=1, minutes=5):
        await send_sms_to_affected_users(
            outage,
            message=f"⚠️ Za 1h awaria {outage.utility_type}. Naładuj urządzenia."
        )
```

**Wartość:**
- Free: Lista awarii (manual refresh)
- Premium: Push 24h + SMS 1h przed (jeśli dotknięty)
- Business: API webhooks + historical data

**Koszty:** 0 PLN (scraping public data)

---

## Roadmapa Implementacji

### Phase 1: Quick Wins (Tygodnie 1-4)
```
✓ Week 1: Daily Newsletter Automation
✓ Week 2: Enhanced GUS Dashboard (25+ variables)
✓ Week 3: Article Filtering & Personalization
✓ Week 4: Ad-Free Experience (Google AdSense)

Deliverable: Premium tier (19 zł) justified
Cost: 0 PLN
Break-even: 18 Premium users
```

### Phase 2: Strategic Bets (Tygodnie 5-12)
```
✓ Weeks 5-6: GIOŚ Air Quality + Alerts
✓ Weeks 7-9: Real Estate Intelligence
✓ Weeks 10-11: Push Notifications
✓ Week 12: SMS Alerts

Deliverable: Premium fully featured
Cost: +130 PLN/mc (SMS ~100, Scraping ~30)
Break-even: 25 Premium users OR 7 Business users
```

### Phase 3: Business Tier (Tygodnie 13-24)
```
✓ Weeks 13-16: Public API + Rate limiting
✓ Weeks 17-19: Custom Reports (Excel/PDF)
✓ Weeks 20-22: Utility Alerts
✓ Weeks 23-24: Polish & Launch

Deliverable: Business tier (99 zł) ready
Total Cost: 330 PLN/mc
Break-even: 18 Premium OR 4 Business
Target: 50 Premium + 5 Business = 1445 PLN/mc (77% margin)
```

---

## Critical Files dla Implementacji

### Backend - Nowe Pliki (8 plików)
1. `/backend/src/integrations/gios_api.py` - GIOŚ smog API
2. `/backend/src/scrapers/real_estate_scraper.py` - OLX/Otodom
3. `/backend/src/scrapers/utility_scraper.py` - Energa/Wodociągi
4. `/backend/src/notifications/push_service.py` - Web Push (VAPID)
5. `/backend/src/notifications/sms_service.py` - SMS (SMSAPI)
6. `/backend/src/reports/generator.py` - Excel/PDF reports
7. `/backend/src/api/endpoints/newsletter.py` - Newsletter preferences
8. `/backend/src/api/v1/business_api.py` - Business API

### Backend - Modyfikacje (3 pliki)
1. `/backend/src/database/schema.py` - Dodać 6 tabel:
   - `AirQuality`
   - `RealEstateListing`
   - `PushSubscription`
   - `UtilityOutage`
   - `APIKey`
   - User.phone, User.sms_quota_used (nowe pola)

2. `/backend/src/api/endpoints/stats.py` - Dodać:
   - `GET /api/stats/multi-metric-comparison`
   - `GET /api/stats/export`

3. `/backend/src/scheduler/scheduler.py` - Dodać 3 joby:
   - `air_quality_job` (co 1h)
   - `real_estate_job` (codziennie 7:00)
   - `utility_outages_job` (co 6h)

### Frontend - Nowe Pliki (6 plików)
1. `/frontend/components/widgets/AirQualityWidget.tsx`
2. `/frontend/components/AdBanner.tsx`
3. `/frontend/src/pages/RealEstatePage.tsx`
4. `/frontend/src/pages/ReportsPage.tsx`
5. `/frontend/src/pages/DeveloperPage.tsx`
6. `/frontend/src/services/pushNotifications.ts`
7. `/frontend/public/sw.js` - Service Worker

### Frontend - Modyfikacje (3 pliki)
1. `/frontend/src/pages/ProfilePage.tsx` - Dodać:
   - Newsletter toggles (daily/weekly)
   - Phone field
   - Push subscription button

2. `/frontend/src/pages/GUSPage.tsx` - Dodać:
   - 20+ nowych zmiennych
   - Multi-metric comparison
   - Premium paywall blur

3. `/frontend/components/NewsFeed.tsx` - Dodać:
   - FilterSidebar (kategorie, tagi, lokalizacje)
   - Premium paywall dla zaawansowanych filtrów

---

## Koszty Miesięczne

```
MVP Baseline:
- OpenAI API: ~100 PLN
- Apify (Facebook): ~50 PLN
- VPS Hosting: ~50 PLN
SUBTOTAL: 200 PLN

Phase 1 (+0 PLN):
- Newsletter (Resend): FREE (3000 emails/mc)
- GUS API: FREE
- AdSense: +revenue
TOTAL: 200 PLN

Phase 2 (+130 PLN):
- GIOŚ API: FREE
- SMS (SMSAPI): ~100 PLN (1000 SMS)
- Real Estate Scraping: ~30 PLN (Apify) OR 0 PLN (własny)
- Push Notifications: FREE (VAPID)
TOTAL: 330 PLN

Phase 3 (+0 PLN):
- API hosting: included w VPS
- Report generation: FREE (openpyxl)
TOTAL: 330 PLN

GRAND TOTAL: 330 PLN/mc
```

---

## Break-even Analysis

```
Miesięczne koszty: 330 PLN

Opcja 1: Premium only
330 PLN ÷ 19 PLN = 18 users

Opcja 2: Business only
330 PLN ÷ 99 PLN = 4 users

Opcja 3: Mix (realistic)
15 Premium (285 PLN) + 1 Business (99 PLN) = 384 PLN ✅

Target (Miesiąc 6):
50 Premium (950 PLN) + 5 Business (495 PLN) = 1445 PLN
Margin: 1445 - 330 = 1115 PLN (77%)
```

---

## Metryki Sukcesu (KPIs)

### Week 4 (Phase 1 Complete)
- [ ] 10+ Daily Newsletter subscribers
- [ ] 50+ sessions na enhanced GUS dashboard
- [ ] AdSense revenue > 0 PLN
- [ ] 3+ Premium trials (7 dni free)

### Week 12 (Phase 2 Complete)
- [ ] 5+ Active Premium subscriptions (95 PLN/mc)
- [ ] 100+ push subscribers
- [ ] 20+ SMS alerts wysłanych
- [ ] 10+ property listings w bazie

### Week 24 (Phase 3 Complete)
- [ ] 1+ Business subscription (99 PLN/mc)
- [ ] 100+ API requests/day
- [ ] Break-even osiągnięte (revenue > 330 PLN)
- [ ] 5+ custom reports wygenerowanych

### Miesiąc 6 (Long-term)
- [ ] 50+ Premium (950 PLN/mc)
- [ ] 5+ Business (495 PLN/mc)
- [ ] Profit: 1115 PLN/mc (77% margin)
- [ ] Churn rate < 10%

---

## Weryfikacja Wdrożenia

### Po każdej fazie - checklist:

**Phase 1 Verification:**
```bash
# Backend
curl -X PUT http://localhost:8000/api/newsletter/preferences \
  -H "Authorization: Bearer {token}" \
  -d '{"frequency": "daily", "enabled": true}'

curl http://localhost:8000/api/stats/multi-metric-comparison?var_ids=60530,60529

curl http://localhost:8000/api/articles/personalized?tags=biznes,transport

# Frontend
- Newsletter toggle w ProfilePage działa
- GUSPage pokazuje 25+ zmiennych
- Free users widzą blur na premium features
- AdSense bannery wyświetlają się dla free users
```

**Phase 2 Verification:**
```bash
# GIOŚ API
curl http://localhost:8000/api/air-quality
curl http://localhost:8000/api/air-quality/trend?days=30

# Real Estate
curl http://localhost:8000/api/real-estate/market-summary

# Push
# Test w przeglądarce - kliknij "Włącz powiadomienia"

# SMS
# Test alert - trigger critical smog event (PM2.5 > 100)
```

**Phase 3 Verification:**
```bash
# API
curl -X GET http://localhost:8000/api/v1/articles \
  -H "X-API-Key: {business_api_key}"

# Reports
curl -X GET http://localhost:8000/api/reports/market?format=xlsx \
  -H "Authorization: Bearer {token}" \
  --output market_report.xlsx

# Utility
curl http://localhost:8000/api/utility/outages
```

---

## Następne Kroki

1. **Zatwierdzenie planu** przez Product Ownera
2. **Phase 1 Week 1** - Start implementacji Daily Newsletter
3. **Setup infrastructure:**
   - Wygenerować VAPID keys dla Web Push
   - Utworzyć konto SMSAPI.pl (200 PLN prepaid)
   - Setup Google AdSense account
4. **Database migrations:**
   - Alembic migration dla nowych tabel
   - Dodać User.phone, User.sms_quota_used fields
5. **Testing:**
   - Unit tests dla nowych endpointów
   - Integration tests dla GIOŚ, Real Estate scrapers
   - E2E tests dla payment flow (Stripe)

---

**Plan przygotowany:** 2026-02-03
**Przewidywany czas wdrożenia:** 24 tygodnie (6 miesięcy)
**Break-even:** Tydzień 12-16 (realistycznie)
**Target profit:** Miesiąc 6 → 1115 PLN/mc (77% margin)
