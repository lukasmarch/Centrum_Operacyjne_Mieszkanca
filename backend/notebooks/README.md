# Facebook Data Analysis - Instrukcja

## 📋 Opis

Notebook `facebook_data_analysis.ipynb` pozwala na:
- ✅ Pobranie ostatnich danych z Apify Facebook Scraper
- ✅ Analizę surowych danych z API
- ✅ Zobaczenie jak dane są parsowane przed zapisem do bazy
- ✅ Porównanie danych Apify z danymi w PostgreSQL
- ✅ Export danych do CSV/JSON

## 🚀 Jak uruchomić

### 1. Instalacja Jupyter Lab

```bash
cd /Users/lukaszmarchlewicz/Desktop/Centrum_Operacyjne_Mieszkańca/backend
pip install jupyterlab pandas sqlmodel httpx
```

### 2. Uruchomienie Jupyter Lab

```bash
jupyter lab
```

### 3. Otwórz notebook

W przeglądarce otwórz:
```
notebooks/facebook_data_analysis.ipynb
```

### 4. Uruchom komórki

Wykonuj komórki po kolei (Shift + Enter) lub:
- **Run All**: Cell → Run All Cells
- **Run Selected**: Shift + Enter

## 📊 Co pokazuje notebook

### Sekcja 1-3: Pobranie danych z Apify
- Lista ostatnich run'ów Facebook scrapera
- Wybór ostatniego udanego run'a
- Pobranie surowych danych JSON

### Sekcja 4-5: Analiza surowych danych
- Struktura danych zwracanych przez Apify
- Dostępne pola (postId, text, url, timestamp, likes, comments, shares)
- Symulacja parsowania jak w `apify_facebook.py`

### Sekcja 6-7: Porównanie i analiza
- Porównanie surowych danych vs. przetworzone
- DataFrame z statystykami engagement
- TOP posty według liczby polubień

### Sekcja 8-9: Dane w bazie
- Połączenie z PostgreSQL
- Pobranie artykułów z bazy
- Porównanie: Apify vs Baza Danych

### Sekcja 10: Export
- Zapis danych do CSV (Apify + Database)
- Zapis surowych danych do JSON
- Pliki zapisywane w `notebooks/exports/`

## 🔑 Wymagane zmienne środowiskowe

Notebook używa konfiguracji z `backend/.env`:

```env
APIFY_API_KEY=apify_api_***********
DATABASE_URL=postgresql://user:pass@localhost/dbname
```

## 📦 Struktura danych

### Surowe dane z Apify (przykład):
```json
{
  "postId": "123456789",
  "text": "Treść posta...",
  "url": "https://facebook.com/...",
  "timestamp": 1704884400,
  "imageUrl": "https://...",
  "likes": 42,
  "comments": 5,
  "shares": 2
}
```

### Dane po parsowaniu (do bazy):
```json
{
  "title": "Treść posta...",
  "url": "https://facebook.com/...",
  "content": "Treść posta...\n\n[42 polubień, 5 komentarzy, 2 udostępnień]",
  "image_url": "https://...",
  "external_id": "fb_123456789",
  "author": "Facebook",
  "published_at": "2024-01-10T12:00:00"
}
```

### Dane w bazie PostgreSQL (tabela `articles`):
```sql
id, source_id, external_id, title, content, summary, url, 
image_url, author, published_at, scraped_at, category, 
tags, location_mentioned, processed
```

## 🛠️ Możliwe rozszerzenia

1. **Wizualizacje**
   ```python
   import matplotlib.pyplot as plt
   df['likes'].hist(bins=20)
   plt.title('Rozkład liczby polubień')
   plt.show()
   ```

2. **Analiza czasowa**
   ```python
   df['hour'] = pd.to_datetime(df['published_at']).dt.hour
   df.groupby('hour')['likes'].mean().plot()
   ```

3. **Word cloud**
   ```python
   from wordcloud import WordCloud
   text = ' '.join(df['content'])
   wordcloud = WordCloud().generate(text)
   ```

## 🐛 Troubleshooting

### Problem: Brak APIFY_API_KEY
**Rozwiązanie**: Dodaj do `backend/.env`:
```env
APIFY_API_KEY=apify_api_***********
```

### Problem: Brak run'ów w Apify
**Rozwiązanie**: Uruchom scraper najpierw:
```python
# W terminalu
cd backend
python -m scripts.run_scraper
```

### Problem: Błąd połączenia z bazą
**Rozwiązanie**: Sprawdź `DATABASE_URL` w `.env` i upewnij się, że PostgreSQL działa

### Problem: Brak danych w bazie
**Rozwiązanie**: Uruchom scraper lub dodaj źródło Facebook do bazy przez API

## 📚 Przydatne komendy

```python
# Lista wszystkich run'ów
runs_data = await get_recent_runs(ACTOR_ID, APIFY_API_KEY, limit=20)

# Pobranie konkretnego run'a
dataset = await get_run_dataset("run_id_tutaj", APIFY_API_KEY)

# Query do bazy
with Session(engine) as session:
    articles = session.exec(
        select(Article).where(Article.source_id == 1)
    ).all()
```

## 📞 Pomoc

Jeśli masz pytania lub problemy, sprawdź:
- Dokumentację Apify: https://docs.apify.com/api/v2
- Kod scrapera: `backend/src/scrapers/apify_facebook.py`
- Schema bazy: `backend/src/database/schema.py`
