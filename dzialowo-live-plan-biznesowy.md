# Działdowo Live - Rozszerzony Koncept Biznesowy

## Spis treści

1. [Analiza obecnego stanu](#analiza-obecnego-stanu)
2. [Propozycje nowych modułów informacyjnych](#propozycje-nowych-modułów-informacyjnych)
3. [Model biznesowy - struktura subskrypcji](#model-biznesowy---struktura-subskrypcji)
4. [Scenariusze użycia](#scenariusze-użycia)
5. [Źródła danych do agregacji](#źródła-danych-do-agregacji)
6. [Przewaga konkurencyjna](#przewaga-konkurencyjna)
7. [Następne kroki](#następne-kroki)

---

## Analiza obecnego stanu

Na podstawie prototypu aplikacja posiada solidną bazę funkcjonalności:

| Funkcja | Opis |
|---------|------|
| **Panel główny** | Podsumowanie AI aktualizowane co 15 minut |
| **Wiadomości** | Agregacja z różnych źródeł (Gmina Rybno, Działdowo.pl, Moje Działdowo) |
| **Pogoda i jeziora** | Temperatura powietrza, wody (19.5°C), warunki wiatrowe |
| **Status dróg** | Informacje w czasie rzeczywistym o utrudnieniach |
| **Wydarzenia** | Kalendarz lokalnych imprez (Dni Działdowa 2024) |

---

## Propozycje nowych modułów informacyjnych

### 1. MODUŁ URZĘDOWY

**Zakres dostarczanych informacji:**

- Kolejka w urzędach (integracja z systemami kolejkowymi lub scraping statusów)
- Terminy składania wniosków (500+, podatki lokalne, deklaracje odpadowe)
- Status złożonych spraw (jeśli API dostępne)
- Dyżury specjalistów (radca prawny, geodeta, rzecznik konsumenta)
- Ogłoszenia przetargowe dla lokalnych firm
- Godziny pracy urzędów i zmiany w harmonogramie

**Przykładowa karta AI:**

> *"Urząd Miasta jutro pracuje krócej (do 14:00). Termin składania deklaracji śmieciowych mija za 5 dni. Obecnie średni czas oczekiwania w okienku podatkowym: 12 minut."*

**Źródła danych:** BIP, ePUAP, strony urzędów gmin, systemy kolejkowe

---

### 2. MODUŁ ZDROWIE I BEZPIECZEŃSTWO

**Zakres dostarczanych informacji:**

- Dyżury aptek (automatycznie aktualizowane z harmonogramu)
- Dostępność lekarzy POZ (jeśli przychodnie udostępnią dane)
- Alerty pogodowe i zagrożenia (burze, upały, smog, przymrozki)
- Jakość powietrza (integracja z GIOŚ)
- Komunikaty sanepidu i policji
- Informacje o szczepieniach i badaniach profilaktycznych
- Numery alarmowe i dyżurne

**Przykładowa karta AI:**

> *"Dziś dyżur apteki: Apteka Pod Orłem (ul. Wolności 12) do 22:00. Jakość powietrza: dobra (AQI 42). Policja informuje o wzmożonych kontrolach na DK13."*

**Źródła danych:** NFZ, GIOŚ, Policja, Sanepid, lokalne apteki

---

### 3. MODUŁ EDUKACJA I RODZINA

**Zakres dostarczanych informacji:**

- Kalendarz szkolny (dni wolne, zebrania rodziców, rekrutacje)
- Jadłospisy w przedszkolach i stołówkach szkolnych
- Zajęcia dodatkowe dla dzieci (bezpłatne i płatne)
- Informacje o żłobkach i miejscach opieki
- Stypendia i programy wsparcia dla rodzin
- Kolonie, półkolonie, obozy letnie
- Konkursy i olimpiady dla uczniów

**Przykładowa karta AI:**

> *"Przypomnienie: jutro zebranie rodziców w SP nr 2 o 17:00. W przedszkolu Słoneczko dziś na obiad: zupa pomidorowa i kotlet z ziemniakami. Ruszył nabór na bezpłatne zajęcia z robotyki."*

**Źródła danych:** Strony szkół i przedszkoli, Facebook placówek, BIP oświatowy

---

### 4. MODUŁ LOKALNY BIZNES I PRACA

**Zakres dostarczanych informacji:**

- Nowe oferty pracy w powiecie (agregacja OLX, Pracuj.pl + lokalne źródła)
- Promocje lokalnych sklepów i usługodawców
- Nowo otwarte biznesy w okolicy
- Targi, jarmarki, kiermasze
- Ogłoszenia rolnicze (skup, ceny płodów rolnych, maszyny)
- Szkolenia i kursy zawodowe
- Dotacje dla przedsiębiorców

**Przykładowa karta AI:**

> *"3 nowe oferty pracy w tym tygodniu: magazynier (Rybno), kasjer (Biedronka Działdowo), kierowca kat. C. W sobotę jarmark na rynku - lokalni producenci."*

**Źródła danych:** OLX, Pracuj.pl, PUP Działdowo, Facebook grup lokalnych

---

### 5. MODUŁ TRANSPORT I MOBILNOŚĆ

**Zakres dostarczanych informacji:**

- Rozkłady PKS/busów w czasie rzeczywistym
- Opóźnienia pociągów (stacja Działdowo)
- Ceny paliw na lokalnych stacjach benzynowych
- Parkingi i ich dostępność
- Planowane remonty dróg i objazdy
- Taxi i przewoźnicy lokalni
- Car-sharing i BlaBlaCar w regionie

**Przykładowa karta AI:**

> *"Autobus do Mławy o 14:30 opóźniony ~10 min. Najtańsze paliwo: Orlen (6.49 zł/l). Uwaga: od poniedziałku zamknięta ul. Lipowa - objazd przez Kolejową."*

**Źródła danych:** PKP, przewoźnicy prywatni, GDDKiA, Google Maps API, e-petrol.pl

---

### 6. MODUŁ SPOŁECZNOŚĆ I KULTURA

**Zakres dostarczanych informacji:**

- Repertuar kina i domu kultury
- Wydarzenia sportowe lokalnych drużyn (Welham Działdowo)
- Zbiórki charytatywne i akcje społeczne
- Grupy wsparcia i organizacje NGO
- Ciekawostki historyczne o regionie
- Wystawy, wernisaże, koncerty
- Spotkania klubów i stowarzyszeń

**Przykładowa karta AI:**

> *"Dziś mecz Welhamu Działdowo o 17:00 - wstęp wolny. W kinie 'Nowe': 'Akademia Pana Kleksa' o 18:00. Trwa zbiórka dla powodzian - punkt w OSP do niedzieli."*

**Źródła danych:** MDK, kluby sportowe, Facebook wydarzeń, strony NGO

---

### 7. MODUŁ NIERUCHOMOŚCI I INWESTYCJE

**Zakres dostarczanych informacji:**

- Nowe ogłoszenia sprzedaży/wynajmu (agregacja OLX, Otodom)
- Plany zagospodarowania przestrzennego
- Inwestycje gminne i powiatowe
- Ceny działek i mieszkań (trendy rynkowe)
- Przetargi na nieruchomości gminne
- Pozwolenia na budowę (kto co buduje)
- Programy dopłat do mieszkań

**Przykładowa karta AI:**

> *"5 nowych mieszkań na wynajem w tym tygodniu (od 1200 zł). Gmina ogłosiła przetarg na działkę przy ul. Polnej. W planie: budowa ścieżki rowerowej Działdowo-Rybno."*

**Źródła danych:** Otodom, OLX, BIP, przetargi gminne, starostwo

---

### 8. MODUŁ PRZYRODA I REKREACJA

**Zakres dostarczanych informacji:**

- Stan jezior (temperatura wody, czystość, zakwity sinic)
- Szlaki turystyczne i ich aktualny stan
- Sezon na grzyby i owoce lasu
- Wypożyczalnie sprzętu wodnego (kajaki, rowery)
- Ogniska i miejsca biwakowe
- Łowiska i informacje dla wędkarzy
- Rezerwaty przyrody i atrakcje naturalne

**Przykładowa karta AI:**

> *"Jezioro Rybieńskie idealne do kąpieli (19.5°C, woda czysta). Na szlaku przez Napromek połamane drzewo - uważać przy km 3. Sezon na kurki w pełni!"*

**Źródła danych:** WIOŚ, Lasy Państwowe, lokalni przewodnicy, użytkownicy aplikacji

---

## Model biznesowy - struktura subskrypcji

### Wariant Freemium dla mieszkańców

| Funkcja | Darmowy | Premium (14.99 zł/mies.) | Premium+ (24.99 zł/mies.) |
|---------|---------|--------------------------|---------------------------|
| Podsumowanie AI | 1x dziennie (rano) | Co 15 minut | Na żywo + push natychmiast |
| Wiadomości | Ostatnie 24h | Pełne archiwum | + personalizacja tematyczna |
| Pogoda i drogi | Dane podstawowe | Rozszerzone prognozy 7 dni | Alerty SMS o zagrożeniach |
| Moduł urzędowy | Tylko ogłoszenia | + kolejki + terminy | + powiadomienia o terminach |
| Praca i biznes | Lista ofert | + filtry + alerty email | Pierwszeństwo dostępu |
| Reklamy | Wyświetlane | Brak reklam | Brak reklam |
| Moduły specjalne | 2 wybrane | Wszystkie 8 modułów | Wszystkie + dostęp API |
| Historia wyszukiwań | 7 dni | 90 dni | Bez limitu |
| Wsparcie | Forum społeczności | Email w 24h | Priorytetowy czat |

### Wariant B2B - Dla firm lokalnych

**Pakiet Firma (99 zł/miesiąc):**
- Wpis w katalogu firm z opisem i zdjęciami
- 2 promocje/miesiąc wyświetlane w module biznesowym
- Podstawowe statystyki wyświetleń
- Oznaczenie "Lokalna firma"

**Pakiet Partner (249 zł/miesiąc):**
- Wyróżniona pozycja w wynikach wyszukiwania
- Nieograniczona liczba promocji
- Powiadomienia push do subskrybentów z okolicy (max 2/tydzień)
- Logo w sekcji "Partnerzy Działdowo Live"
- Rozszerzone statystyki i analityka
- Dedykowany opiekun konta

**Pakiet Premium Biznes (499 zł/miesiąc):**
- Wszystko z Pakietu Partner
- Artykuły sponsorowane (2/miesiąc)
- Integracja z systemem rezerwacji/zamówień
- Raporty o konkurencji i trendach lokalnych
- Pierwszeństwo w powiadomieniach branżowych

### Wariant Instytucjonalny

**Dla urzędów, szkół i instytucji publicznych (ceny negocjowane):**

- Priorytetowe wyświetlanie komunikatów oficjalnych
- Panel administracyjny do zarządzania treścią
- Statystyki dotarcia do mieszkańców
- Integracja z istniejącymi systemami (ePUAP, dziennik elektroniczny)
- Możliwość wysyłki alertów kryzysowych
- Raportowanie dla władz gminy/powiatu
- Szkolenie dla pracowników

**Orientacyjne ceny:**
- Gmina/miasto: 500-1500 zł/miesiąc
- Szkoła/przedszkole: 100-300 zł/miesiąc
- Przychodnia/instytucja: 200-500 zł/miesiąc

### Pakiety sezonowe

**"Lato nad jeziorem" (29 zł/sezon czerwiec-sierpień):**
- Codzienny raport o stanie jezior
- Prognoza pogody na weekend
- Wydarzenia i atrakcje w okolicy
- Restauracje, lodziarnie, wypożyczalnie

**"Grzybiarza" (19 zł/sezon wrzesień-październik):**
- Mapa grzybowych łowisk
- Pogoda dla grzybiarzy
- Porady i ostrzeżenia
- Punkty skupu grzybów

---

## Scenariusze użycia

### Scenariusz 1: Mama z dwójką dzieci (Premium)

**Profil:** Agnieszka, 35 lat, dwoje dzieci (przedszkole i szkoła podstawowa)

**Poranek (7:00)** - Push notification z podsumowaniem AI:

> *"Dzień dobry Agnieszko! Dziś w przedszkolu Słoneczko dzień bez zabawek. SP nr 2 - skrócone lekcje do 12:00 (rada pedagogiczna). Temperatura 22°C, idealna na plac zabaw po szkole. Wieczorem bajki w bibliotece o 17:00 - wstęp wolny."*

**W ciągu dnia (12:30)** - Alert:

> *"Przypomnienie: odbiór dzieci ze szkoły o 12:00 (dziś skrócone lekcje)"*

**Wartość:** Agnieszka nigdy nie przegapi ważnych informacji, oszczędza czas na przeglądaniu Facebooka szkoły.

---

### Scenariusz 2: Senior emeryt (Premium+ z dużą czcionką)

**Profil:** Stanisław, 72 lata, mieszka sam, ograniczona mobilność

**Funkcja specjalna:** Uproszczony widok "Dla Seniora" z dużą czcionką

**Poranna karta AI (8:00):**

> *"Dzień dobry Panie Stanisławie! Dziś dyżur apteki do 22:00 przy ul. Wolności (Apteka Pod Orłem). Jutro o 10:00 bezpłatne mierzenie ciśnienia w przychodni przy Kolejowej. Chleb w piekarni Kłos w promocji: 3.99 zł. Pogoda: słonecznie, 24°C."*

**Alert SMS (opcjonalny):**

> *"UWAGA: Burze z gradem po 18:00. Zostań w domu."*

**Wartość:** Rzetelna, prosta informacja. Zero szumu informacyjnego. Poczucie bezpieczeństwa.

---

### Scenariusz 3: Lokalny przedsiębiorca - kamieniarz (Pakiet Partner B2B)

**Profil:** Marek, właściciel firmy kamieniarskiej, szuka zleceń

**Push o 8:00:**

> *"Nowy przetarg w Twoim regionie: Gmina Rybno szuka wykonawcy na renowację pomnika przy kościele. Szacowana wartość: 45 000 zł. Termin składania ofert: 15.01. [Zobacz szczegóły]"*

**Statystyki miesięczne:**

> *"Twoja firma była wyświetlona 847 razy. 23 osoby kliknęły w numer telefonu. Najpopularniejsza usługa: nagrobki."*

**Wartość:** Nie przegapi okazji biznesowej, dociera do lokalnych klientów.

---

### Scenariusz 4: Turysta/działkowiec weekendowy

**Profil:** Tomek z Warszawy, ma działkę nad jeziorem, przyjeżdża w weekendy

**Pakiet:** "Lato nad jeziorem" (sezonowy)

**Piątkowy raport (17:00):**

> *"Weekend nad Jeziorem Rybieńskim: Temperatura wody 21°C - idealna! Prognoza: sobota słonecznie 28°C, niedziela możliwe przelotne opady po 15:00. W sobotę festyn w Rybnie od 12:00 - koncerty, food trucki. Uwaga: DW538 korek przy wjeździe do Działdowa (remont)."*

**Wartość:** Planuje weekend z wyprzedzeniem, wie czego się spodziewać.

---

### Scenariusz 5: Młody mieszkaniec szukający pracy

**Profil:** Kasia, 24 lata, szuka pierwszej pracy po studiach

**Codzienny alert (9:00):**

> *"Nowe oferty pracy w promieniu 30 km: Asystentka biura (Urząd Miasta Działdowo) - 4200 zł brutto, Księgowa (firma XYZ Rybno) - 5000 zł brutto. 2 oferty pasują do Twojego profilu!"*

**Wartość:** Agregacja ofert z wielu źródeł, personalizacja według umiejętności.

---

## Źródła danych do agregacji

| Kategoria | Źródła danych | Metoda pozyskania |
|-----------|---------------|-------------------|
| **Wiadomości** | Strony gmin, lokalne portale (dzialowo.pl, etc.), grupy Facebook | Scraping, Facebook API |
| **Urząd** | BIP, ePUAP, strony urzędów, systemy kolejkowe | Scraping, ewentualne API |
| **Pogoda** | IMGW API, lokalne stacje meteo | API, scraping |
| **Drogi** | GDDKiA, Google Maps, zgłoszenia użytkowników | API, crowdsourcing |
| **Praca** | OLX, Pracuj.pl, PUP Działdowo, lokalne ogłoszenia | Scraping, API |
| **Nieruchomości** | Otodom, OLX, przetargi gminne | Scraping, BIP |
| **Zdrowie** | NFZ, apteki, GIOŚ | API, scraping harmonogramów |
| **Transport** | PKP IC, przewoźnicy prywatni, e-petrol.pl | API, scraping |
| **Edukacja** | Strony szkół, dzienniki elektroniczne, Facebook | Scraping, partnerstwa |
| **Kultura/sport** | MDK, kluby sportowe, Facebook wydarzenia | Scraping, partnerstwa |
| **Jeziora** | WIOŚ, lokalne pomiary, użytkownicy | API WIOŚ, crowdsourcing |

---

## Przewaga konkurencyjna

### 1. AI jako inteligentny kurator
- Nie spam informacyjny, tylko to co istotne dla konkretnego użytkownika
- Weryfikacja źródeł i eliminacja fake news
- Priorytetyzacja według ważności i pilności

### 2. Lokalna głębia informacji
- Żaden ogólnopolski portal nie dostarczy takiej szczegółowości
- Znajomość lokalnych realiów i kontekstu
- Informacje niedostępne nigdzie indziej (kolejki w urzędzie, stan jezior)

### 3. Wiarygodność i rzetelność
- Transparentne źródła każdej informacji
- Algorytm weryfikacji sprzecznych doniesień
- Brak clickbaitów i sensacji

### 4. Personalizacja na poziomie jednostki
- Każdy mieszkaniec ma "swojego" asystenta informacyjnego
- Uczenie się preferencji użytkownika
- Powiadomienia dopasowane do stylu życia

### 5. Dostępność techniczna
- Aplikacja mobilna (iOS/Android)
- Wersja webowa
- Opcja SMS dla seniorów
- Tryb offline (cache najważniejszych informacji)

### 6. Model społecznościowy
- Użytkownicy mogą zgłaszać informacje (korki, awarie, wydarzenia)
- System weryfikacji zgłoszeń przez AI i moderatorów
- Budowanie lokalnej społeczności

---

## Następne kroki

### Faza 1: Walidacja (1-2 miesiące)

- [ ] Ankieta wśród mieszkańców: które moduły najważniejsze?
- [ ] Wywiady z potencjalnymi użytkownikami (10-15 osób)
- [ ] Analiza konkurencji i podobnych rozwiązań
- [ ] Określenie MVP (Minimum Viable Product)

### Faza 2: Partnerstwa (2-3 miesiące)

- [ ] Rozmowy z Urzędem Miasta Działdowo
- [ ] Kontakt ze szkołami i przedszkolami
- [ ] Negocjacje z przychodnią/aptekami
- [ ] Pozyskanie pierwszych partnerów biznesowych

### Faza 3: Rozwój MVP (3-4 miesiące)

- [ ] Implementacja 3 najpopularniejszych modułów
- [ ] Integracja z minimum 5 źródłami danych
- [ ] Podstawowy system subskrypcji
- [ ] Aplikacja mobilna (React Native lub Flutter)

### Faza 4: Beta-testy (2 miesiące)

- [ ] Rekrutacja 100 beta-testerów
- [ ] 3 miesiące darmowego dostępu Premium
- [ ] Zbieranie feedbacku i iteracja
- [ ] Optymalizacja algorytmów AI

### Faza 5: Soft launch (1 miesiąc)

- [ ] Oficjalne uruchomienie dla mieszkańców Działdowa
- [ ] Kampania marketingowa lokalna
- [ ] Monitoring i szybkie reagowanie na problemy

### Faza 6: Skalowanie (6+ miesięcy)

- [ ] Ekspansja na sąsiednie gminy i powiaty
- [ ] Rozwój kolejnych modułów
- [ ] Program poleceń dla użytkowników
- [ ] Poszukiwanie inwestora lub grantu

---

## Metryki sukcesu

| Metryka | Cel po 6 miesiącach | Cel po 12 miesiącach |
|---------|---------------------|----------------------|
| Aktywni użytkownicy | 1 000 | 3 000 |
| Subskrybenci Premium | 100 (10%) | 450 (15%) |
| Partnerzy biznesowi | 15 | 50 |
| Instytucje publiczne | 3 | 10 |
| NPS (Net Promoter Score) | 40+ | 50+ |
| Przychód miesięczny | 5 000 zł | 20 000 zł |

---

## Kontakt i zespół

**Projekt:** Działdowo Live - Centrum Operacyjne Mieszkańca

**Wizja:** Każdy mieszkaniec Działdowa ma dostęp do rzetelnych, spersonalizowanych informacji lokalnych, które ułatwiają codzienne życie.

**Misja:** Wykorzystanie sztucznej inteligencji do agregacji, weryfikacji i dostarczania najważniejszych informacji lokalnych w przystępnej formie.

---

*Dokument wygenerowany: styczeń 2026*
*Wersja: 1.0*
