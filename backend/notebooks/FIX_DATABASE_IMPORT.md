# Rozwiązanie problemu z importem bazy danych

## Problem
Komórka "Sprawdź dane w bazie danych" w notebooku `facebook_data_analysis.ipynb` pokazuje błąd:
```
ModuleNotFoundError: No module named 'src'
```

## Rozwiązanie

Użyj pliku helpera `database_helper.py` zamiast importować bezpośrednio z `database.schema`.

### Zamień komórkę z:
```python
from sqlmodel import create_engine, Session, select
from database.schema import Article, Source

engine = create_engine(settings.DATABASE_URL, echo=False)
```

### Na:
```python
from sqlmodel import Session, select
from database_helper import Source, Article, get_database_connection

# Połącz z bazą używając helpera
engine = get_database_connection(settings.DATABASE_URL)
```

## Pełna poprawiona komórka

Zamień całą komórkę nr 8 ("Sprawdź dane w bazie danych") na:

```python
from sqlmodel import Session, select
from database_helper import Source, Article, get_database_connection

# Połącz z bazą
print("🔌 Łączenie z bazą danych...\\n")

try:
    engine = get_database_connection(settings.DATABASE_URL)
    
    with Session(engine) as session:
        # Znajdź źródło Facebook
        statement = select(Source).where(Source.type == "social_media")
        fb_sources = session.exec(statement).all()
        
        print("📱 ŹRÓDŁA FACEBOOK W BAZIE:\\n")
        for source in fb_sources:
            print(f"  • {source.name} (ID: {source.id})")
            print(f"    URL: {source.url}")
            print(f"    Last scraped: {source.last_scraped}")
            print(f"    Config: {source.scraping_config}")
            print()
        
        if fb_sources:
            # Pobierz artykuły z pierwszego źródła
            source_id = fb_sources[0].id
            
            statement = select(Article).where(
                Article.source_id == source_id
            ).order_by(Article.scraped_at.desc()).limit(10)
            
            articles = session.exec(statement).all()
            
            print(f"\\n📰 OSTATNIE {len(articles)} ARTYKUŁÓW Z BAZY:\\n")
            
            for article in articles:
                print(f"  • {article.title[:60]}...")
                print(f"    ID: {article.id} | External ID: {article.external_id}")
                print(f"    Published: {article.published_at}")
                print(f"    Scraped: {article.scraped_at}")
                print(f"    Category: {article.category} | Tags: {article.tags}")
                print(f"    Processed: {article.processed}")
                print()
            
            # Stwórz DataFrame z bazy
            articles_df = pd.DataFrame([
                {
                    'id': a.id,
                    'title': a.title,
                    'external_id': a.external_id,
                    'published_at': a.published_at,
                    'scraped_at': a.scraped_at,
                    'category': a.category,
                    'processed': a.processed
                }
                for a in articles
            ])
            
            print("\\n📊 PODSUMOWANIE ARTYKUŁÓW W BAZIE:\\n")
            display(articles_df)
        else:
            print("\\n❌ Brak źródeł Facebook w bazie")
            print("Dodaj źródło przez API lub bezpośrednio do bazy danych")
            
except Exception as e:
    print(f"\\n❌ BŁĄD połączenia z bazą: {e}")
    print(f"\\n💡 Sprawdź:")
    print(f"  1. Czy PostgreSQL działa")
    print(f"  2. Czy DATABASE_URL w .env jest poprawny")
    print(f"  3. DATABASE_URL: {settings.DATABASE_URL[:50]}...")
```

## Dlaczego to rozwiązuje problem?

- **database_helper.py** definiuje klasy `Source` i `Article` bezpośrednio, bez importowania z `src.config`
- Unikamy problemu z zagnieżdżonymi importami modułu `database`
- Helper działa zarówno w Jupyter Lab jak i w zwykłych skryptach Python

## Weryfikacja

Po zmianie, uruchom komórkę ponownie. Jeśli wszystko działa poprawnie, zobaczysz:
```
🔌 Łączenie z bazą danych...

📱 ŹRÓDŁA FACEBOOK W BAZIE:
  • Facebook - Syla (ID: 1)
    ...
```
