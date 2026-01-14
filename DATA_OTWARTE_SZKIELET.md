# Szkielet Modułów Danych Otwartych - Centrum Operacyjne Mieszkańca

## 🎯 Przegląd
Integracja danych z API GUS (api.stat.gov.pl) i dane.gov.pl dla Powiatu Działdowskiego.

---

## 📊 MODUŁ 1: Demografia & Statystyki (GUS API)

### Źródło danych
- **API:** `https://bdl.stat.gov.pl/api/v1`
- **Unit ID:** `042815403000` (Powiat działdowski)
- **Częstotliwość:** Dane aktualizowane kwartalnie/rocznie przez GUS

### Dane dla użytkowników

#### 1.1 Ludność
```
📈 Statystyki:
- Ludność ogółem (+ trend rok/rok)
- Struktura wiekowa (dzieci 0-17, prod. 18-64, emeryci 65+)
- Gęstość zaludnienia (osoby/km²)
- Przyrost naturalny
- Migracje (napływ/odpływ)

💡 Wartość: "Ile osób mieszka w moim powiecie? Czy populacja rośnie?"
```

#### 1.2 Rynek Pracy
```
📊 Wskaźniki:
- Stopa bezrobocia rejestrowanego (%)
- Liczba bezrobotnych (+ trend)
- Oferty pracy (aktywne ogłoszenia)
- Przeciętne wynagrodzenie brutto

💡 Wartość: "Jak wygląda rynek pracy? Czy łatwo znaleźć pracę?"
```

### Implementacja
```python
# backend/src/integrations/gus_api.py
class GUSDataService:
    BASE_URL = "https://bdl.stat.gov.pl/api/v1"
    UNIT_ID_DZIALDOWO = "042815403000"

    # Variable IDs (przykładowe)
    VAR_POPULATION = "72305"      # Ludność ogółem
    VAR_UNEMPLOYMENT = "P3687"    # Stopa bezrobocia

    async def get_population_stats(self):
        """Pobiera dane demograficzne"""

    async def get_employment_stats(self):
        """Pobiera dane o rynku pracy"""
```

---

## 🏠 MODUŁ 2: Nieruchomości & Mienie Komunalne (dane.gov.pl)

### Źródło danych
- **Portal:** dane.gov.pl (wyszukiwanie: "nieruchomości działdowo", "mienie komunalne")
- **Format:** CSV, JSON
- **Częstotliwość:** Miesięczna aktualizacja przez Starostwo/Urząd

### Dane dla użytkowników

#### 2.1 Ceny Transakcyjne (RCiWN)
```
💰 Informacje:
- Średnia cena m² mieszkania (powiat)
- Ceny gruntów (działki budowlane)
- Trendy cen (rok/rok, kwartał/kwartał)
- Porównanie z województwem/krajem

💡 Wartość: "Ile kosztuje mieszkanie w mojej okolicy?"
```

#### 2.2 Mienie do Sprzedaży/Wynajmu
```
🏢 Ogłoszenia:
- Lokale użytkowe do wynajęcia
- Działki do sprzedaży
- Mieszkania komunalne
- Przetargi na nieruchomości

💡 Wartość: "Czy gmina sprzedaje jakieś działki/lokale?"
```

#### 2.3 Pozwolenia na Budowę
```
🏗️ Inwestycje:
- Nowe pozwolenia na budowę (ostatnie 30 dni)
- Mapa inwestycji (gdzie się buduje)
- Rodzaj inwestycji (budynki mieszkalne, usługowe)

💡 Wartość: "Co się buduje w mojej okolicy?"
```

### Implementacja
```python
# backend/src/integrations/dane_gov_pl.py
class DaneGovPlService:
    API_URL = "https://api.dane.gov.pl/1.4"

    async def search_datasets(self, query: str, category: str = None):
        """Wyszukuje datasety"""

    async def get_real_estate_prices(self):
        """Ceny nieruchomości (RCiWN)"""

    async def get_building_permits(self):
        """Pozwolenia na budowę (RWDZ)"""

    async def get_municipal_property(self):
        """Mienie komunalne do sprzedaży/wynajmu"""
```

---

## 💰 MODUŁ 3: Finanse Publiczne (dane.gov.pl)

### Źródło danych
- **Datasety:** Sprawozdania budżetowe JST (Rb-27S, Rb-28S)
- **Jednostki:** Gmina Rybno, Powiat Działdowski
- **Częstotliwość:** Miesięczna/kwartalna

### Dane dla użytkowników

#### 3.1 Budżet Gminy/Powiatu
```
💵 Przegląd:
- Dochody całkowite (+ podział na kategorie)
- Wydatki całkowite (+ podział na dziedziny)
- Saldo budżetu
- Wykonanie budżetu (% planu)

📊 Kategorie wydatków:
- Oświata i edukacja
- Transport i drogi
- Kultura i sport
- Ochrona środowiska
- Bezpieczeństwo publiczne

💡 Wartość: "Na co gmina wydaje pieniądze? Ile idzie na drogi/edukację?"
```

#### 3.2 Inwestycje
```
🏗️ Wydatki majątkowe:
- Lista inwestycji (nazwa, kwota, status)
- Trendy inwestycji (rok/rok)
- Najważniejsze projekty

💡 Wartość: "Jakie inwestycje planuje gmina?"
```

#### 3.3 Dług Publiczny
```
📉 Zadłużenie:
- Dług JST (kwota, % dochodów)
- Trend zadłużenia
- Spłaty kredytów/pożyczek

💡 Wartość: "Jak wysoko zadłużona jest gmina?"
```

### Implementacja
```python
# backend/src/integrations/public_finance.py
class PublicFinanceService:

    async def get_budget_summary(self, unit: str = "Rybno"):
        """Podsumowanie budżetu JST"""

    async def get_investments(self):
        """Lista inwestycji majątkowych"""

    async def get_debt_stats(self):
        """Zadłużenie JST"""
```

---

## 📢 MODUŁ 4: Przetargi & Zamówienia (dane.gov.pl)

### Źródło danych
- **Portal:** Biuletyn Zamówień Publicznych (BZP)
- **Datasety:** Ogłoszenia BZP, plany postępowań
- **Częstotliwość:** Real-time (nowe ogłoszenia codziennie)

### Dane dla użytkowników

#### 4.1 Aktualne Przetargi
```
📋 Ogłoszenia:
- Tytuł przetargu
- Zamawiający (gmina, powiat, urząd)
- Wartość szacunkowa
- Termin składania ofert
- Status (nowy, w toku, rozstrzygnięty)

💡 Wartość: "Jakie przetargi ogłasza gmina? Dla firm lokalnych."
```

#### 4.2 Rozstrzygnięte Przetargi
```
✅ Wyniki:
- Wygrany wykonawca
- Cena oferty
- Przedmiot zamówienia

💡 Wartość: "Kto wygrał przetarg na remont drogi w mojej gminie?"
```

### Implementacja
```python
# backend/src/integrations/bzp_service.py
class BZPService:

    async def get_active_tenders(self, region: str = "Działdowo"):
        """Aktualne przetargi dla regionu"""

    async def get_tender_results(self):
        """Rozstrzygnięte przetargi"""
```

---

## 🏫 MODUŁ 5: Edukacja (GUS API)

### Źródło danych
- **API:** BDL GUS
- **Kategoria:** Edukacja i Wychowanie
- **Częstotliwość:** Roczna (wrzesień - początek roku szkolnego)

### Dane dla użytkowników

#### 5.1 Szkoły i Placówki
```
🏫 Infrastruktura:
- Liczba szkół (podstawowe, ponadpodstawowe)
- Liczba przedszkoli
- Liczba żłobków

💡 Wartość: "Ile szkół jest w powiecie?"
```

#### 5.2 Uczniowie i Nauczyciele
```
👨‍🎓 Statystyki:
- Liczba uczniów (podział na szkoły)
- Liczba nauczycieli
- Stosunek uczniów/nauczyciel (jakość edukacji)

💡 Wartość: "Jak duże są klasy w lokalnych szkołach?"
```

### Implementacja
```python
# backend/src/integrations/gus_api.py (rozszerzenie)
class GUSDataService:
    VAR_SCHOOLS = "P1234"         # Liczba szkół
    VAR_STUDENTS = "P5678"        # Liczba uczniów

    async def get_education_stats(self):
        """Dane o edukacji"""
```

---

## 🚗 MODUŁ 6: Transport & Infrastruktura (GUS + dane.gov.pl)

### Źródło danych
- **GUS API:** Drogi, pojazdy, wypadki
- **dane.gov.pl:** Wykazy dróg powiatowych, remonty
- **Częstotliwość:** Kwartalna (GUS), miesięczna (dane.gov.pl)

### Dane dla użytkowników

#### 6.1 Drogi Publiczne
```
🛣️ Infrastruktura:
- Długość dróg powiatowych (km)
- Drogi o nawierzchni twardej (%)
- Remonty dróg (bieżące i planowane)

💡 Wartość: "Jakie drogi są remontowane?"
```

#### 6.2 Pojazdy i Wypadki
```
🚙 Statystyki:
- Liczba zarejestrowanych pojazdów
- Wypadki drogowe (liczba, ofiary)
- Punkty niebezpieczne (mapa wypadków)

💡 Wartość: "Ile wypadków w powiecie? Gdzie są niebezpieczne miejsca?"
```

### Implementacja
```python
# backend/src/integrations/transport_data.py
class TransportDataService:

    async def get_road_infrastructure(self):
        """Dane o drogach"""

    async def get_accident_stats(self):
        """Statystyki wypadków"""
```

---

## 🏥 MODUŁ 7: Zdrowie (GUS API)

### Źródło danych
- **API:** BDL GUS - Ochrona Zdrowia
- **Częstotliwość:** Roczna

### Dane dla użytkowników

#### 7.1 Placówki Medyczne
```
🏥 Infrastruktura:
- Liczba szpitali
- Liczba przychodni POZ
- Liczba aptek
- Łóżka szpitalne (na 10k mieszkańców)

💡 Wartość: "Jak wygląda dostęp do służby zdrowia?"
```

### Implementacja
```python
# backend/src/integrations/gus_api.py (rozszerzenie)
class GUSDataService:
    async def get_health_stats(self):
        """Dane o ochronie zdrowia"""
```

---

## 🗄️ Struktura Backend

```
backend/
├── src/
│   ├── integrations/          ← NOWY FOLDER
│   │   ├── __init__.py
│   │   ├── gus_api.py         ← GUS API client
│   │   ├── dane_gov_pl.py     ← dane.gov.pl client
│   │   ├── public_finance.py  ← Finanse publiczne
│   │   ├── bzp_service.py     ← Przetargi BZP
│   │   └── transport_data.py  ← Transport/infrastruktura
│   │
│   ├── database/
│   │   └── schema.py          ← Nowe tabele:
│   │                             - gus_statistics
│   │                             - real_estate_prices
│   │                             - budget_data
│   │                             - tenders
│   │
│   ├── scheduler/
│   │   ├── scheduler.py       ← Dodaj nowe joby
│   │   ├── gus_job.py         ← Pobieranie danych GUS (1x dziennie)
│   │   └── dane_job.py        ← Pobieranie dane.gov.pl (1x dziennie)
│   │
│   └── api/
│       └── main.py            ← Nowe endpointy:
│                                 GET /api/stats/demographics
│                                 GET /api/stats/employment
│                                 GET /api/real-estate/prices
│                                 GET /api/budget/summary
│                                 GET /api/tenders
```

---

## 📋 Propozycja Priorytetów (Dla użytkownika)

### SPRINT 1 (Tydzień 1-2): Dane GUS - Demografia & Praca
**Cel:** "Ile osób mieszka w powiecie? Jak wygląda rynek pracy?"

**Tasks:**
1. [ ] Integracja z GUS API (BDL)
2. [ ] Endpoint: `/api/stats/demographics`
3. [ ] Endpoint: `/api/stats/employment`
4. [ ] Widget Frontend: Statystyki demograficzne
5. [ ] Widget Frontend: Stopa bezrobocia + oferty pracy

**Wartość:** Podstawowe dane statystyczne - fundament dla innych modułów.

---

### SPRINT 2 (Tydzień 3-4): Nieruchomości & Pozwolenia
**Cel:** "Ile kosztuje mieszkanie? Co się buduje w okolicy?"

**Tasks:**
1. [ ] Integracja dane.gov.pl API
2. [ ] Wyszukiwanie datasetów: RCiWN (ceny), RWDZ (pozwolenia)
3. [ ] Endpoint: `/api/real-estate/prices`
4. [ ] Endpoint: `/api/real-estate/permits`
5. [ ] Widget Frontend: Ceny nieruchomości (trend)
6. [ ] Widget Frontend: Mapa inwestycji (pozwolenia na budowę)

**Wartość:** Informacje praktyczne - mieszkańcy szukają mieszkań/działek.

---

### SPRINT 3 (Tydzień 5-6): Finanse Publiczne & Przetargi
**Cel:** "Na co gmina wydaje pieniądze? Jakie przetargi są dostępne?"

**Tasks:**
1. [ ] Dataset: Sprawozdania budżetowe JST (Rb-27S/Rb-28S)
2. [ ] Endpoint: `/api/budget/summary`
3. [ ] Endpoint: `/api/budget/investments`
4. [ ] Integracja BZP (przetargi)
5. [ ] Endpoint: `/api/tenders`
6. [ ] Widget Frontend: Budżet gminy (wykres kołowy wydatków)
7. [ ] Widget Frontend: Aktualne przetargi (lista)

**Wartość:** Transparentność finansowa - obywatele widzą jak wydawane są pieniądze.

---

### SPRINT 4 (Tydzień 7-8): Edukacja, Zdrowie, Transport (GUS)
**Cel:** "Kompleksowe statystyki GUS - pełny obraz powiatu"

**Tasks:**
1. [ ] Rozszerzenie GUS API: edukacja, zdrowie, transport
2. [ ] Endpoint: `/api/stats/education`
3. [ ] Endpoint: `/api/stats/health`
4. [ ] Endpoint: `/api/stats/transport`
5. [ ] Widget Frontend: Dashboard statystyk GUS (wielofunkcyjny)

**Wartość:** Pełny profil powiatu - dane do planowania rodzinnego, biznesowego.

---

## 💰 Koszty Integracji

### API GUS
- **Darmowe:** Do 100 zapytań/15 min (bez rejestracji)
- **Z rejestracją (FREE):** Wyższe limity (~1000/dzień)
- **Koszt:** 0 PLN/miesiąc ✅

### dane.gov.pl
- **Darmowe:** Pełen dostęp bez klucza API
- **Koszt:** 0 PLN/miesiąc ✅

### Całkowity koszt dodatkowy: **0 PLN/miesiąc** 🎉

---

## 🎯 Wartość dla Użytkowników

### Dla Mieszkańców:
- ✅ "Ile kosztuje mieszkanie w mojej okolicy?"
- ✅ "Czy gmina sprzedaje działki?"
- ✅ "Jakie inwestycje planuje gmina?"
- ✅ "Gdzie jest praca? (stopa bezrobocia)"

### Dla Firm:
- ✅ Przetargi publiczne (nowe szanse biznesowe)
- ✅ Statystyki rynku pracy (rekrutacja)
- ✅ Dane demograficzne (analiza rynku)

### Dla Samorządu:
- ✅ Transparentność finansowa
- ✅ Promocja inwestycji
- ✅ Udostępnienie danych obywatelom

---

## 📞 Następne Kroki

**Pytanie do Ciebie:**
1. Który moduł budujemy pierwszy? (Sugestia: **Demografia & Praca** - najprostszy start)
2. Czy masz dostęp do konkretnych datasetów z Działdowa/Rybna? (np. budżet gminy)
3. Czy interesuje Cię mapa inwestycji (pozwolenia na budowę)? Wymaga GIS/leaflet.

**Ready to start?** 🚀
