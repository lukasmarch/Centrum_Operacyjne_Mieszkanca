# Podsumowanie Projektu: Gmina Rybno Dashboard

## Backend (Python)
Kluczowe pliki odpowiadające za pobieranie i przetwarzanie danych.

### Skrapowanie (Pobieranie Danych)
- **`scraping/run_rybno_scrape.py`**: **Główny skrypt.** Pobiera dane ze strony głównej `polskawliczbach.pl/gmina_Rybno...`. Używa API Firecrawl. Jeśli znajdzie lokalny plik `rybno_data.json`, wczytuje go zamiast pobierać dane z sieci.
- **`scraping/crawl_rybno.py`**: Skrypt do "głębokiego" skrapowania. Pobiera stronę główną ORAZ podstrony (szczegóły edukacji, demografii itp.). Używany rzadziej, gdy potrzebujemy bardziej szczegółowych danych.
- **`scraping/firecrawl_client.py`**: Klient API do Firecrawl. Obsługuje komunikację z zewnętrznym serwisem skrapującym.

### Parsowanie (Przetwarzanie Danych)
- **`scraping/parser.py`**: **Serce logiki.** Zawiera klasy i wyrażenia regularne (Regex), które zamieniają surowy tekst (Markdown) ze strony na ustrukturyzowane dane (obiekty Python/JSON). To tutaj naprawialiśmy logikę wyciągania budżetu.
- **`scraping/models.py`**: Definicje modeli danych (Pydantic). Określają, jakie pola ma mieć "Demografia", "Finanse", czy "Nieruchomości".
- **`reparse.py`**: Skrypt pomocniczy. Pozwala ponownie przetworzyć pobrany już plik `rybno_data.json` używając zaktualizowanego `parser.py`. Służy do szybkiego testowania poprawek w parsu without ponownego skrapowania.

### Dane
- **`rybno_data.json`**: Główny plik z danymi w korzeniu projektu. Zawiera surowe dane ze skrapowania (`raw_scrape`) oraz przetworzone dane (`structured_data`).
- **`frontend/data.json`**: Kopia pliku `rybno_data.json` w katalogu frontendu. To z tego pliku korzysta strona WWW.

---

## Frontend (HTML/JS/CSS)
Wizualizacja danych w przeglądarce.

- **`frontend/index.html`**: Struktura strony. Zawiera układ Dashboardu, menu boczne i kontenery na wykresy.
- **`frontend/app.js`**: Logika frontendu.
    - Wczytuje `data.json`.
    - Renderuje kafelki z danymi (Liczba ludności, Budżet).
    - Rysuje wykresy (Chart.js) – w tym nowe wykresy historyczne budżetu.
- **`frontend/styles.css`**: Wygląd strony. Styl "Glassmorphism", kolory, cienie i układ responsywny.

---

## Jak uruchomić?

1. **Pobranie danych (opcjonalne, jeśli masz json):**
   ```bash
   python scraping/run_rybno_scrape.py
   ```
2. **Aktualizacja parsera (jeśli zmieniłeś parser.py):**
   ```bash
   python reparse.py
   ```
3. **Uruchomienie strony:**
   ```bash
   cd frontend
   python3 -m http.server 8081
   # Otwórz http://localhost:8081
   ```
