"""
Manifest migracji (audyt 10–11.10.2026, E5): JEDNA lista wszystkich skryptów w tym katalogu.

Po co: skrypty były uruchamiane ręcznie, żaden nie zapisywał, że poszedł, a `alembic_version`
stoi od lutego na tej samej wartości w każdej bazie. Rozjazd schematu narastał po cichu
(18.08: lokalna baza o 3 tabele i 7 kolumn za produkcją). Runner (`scripts/migrate.py`) zapisuje
wykonane migracje w `schema_migrations` i potrafi powiedzieć, czego brakuje.

Dwa rodzaje:
  • `schema` — zmienia strukturę (tabele, kolumny, indeksy); runner uruchamia je w kolejności z tej listy.
    Skrypt ma być idempotentny (`IF NOT EXISTS`) i addytywny, bo idzie na produkcję PRZED kodem.
  • `data` — operacja na DANYCH (czyszczenie, źródła, RODO). Runner NIGDY ich nie uruchamia:
    wcześniej jedno `for f in *.py` wyczyściłoby bazę. Uruchamia je człowiek, świadomie, pojedynczo.

Nowa migracja = plik `add_*.py` + jedna linia TUTAJ. `test_migration_registry` (CI) czerwieni,
gdy plik nie ma wpisu albo wpis nie ma pliku. Skrypt łączący schemat z danymi rozdziel na dwa.
"""
from dataclasses import dataclass

SCHEMA = "schema"
DATA = "data"


@dataclass(frozen=True)
class Migration:
    name: str
    kind: str
    date: str
    note: str = ""


# Kolejność = kolejność dodania do repozytorium (git). Daty to dzień dodania skryptu.
MANIFEST: list[Migration] = [
    Migration("add_event_unique_constraint", SCHEMA, "2026-01-14"),
    Migration("clean_database", DATA, "2026-01-14", "czyści artykuły, wydarzenia i podsumowania — NIGDY na produkcji"),
    Migration("remove_duplicate_events", DATA, "2026-01-14", "martwy od 21.08.2026 (zastąpiony przez scripts/dedupe_events.py)"),
    Migration("add_gus_database_first_tables", SCHEMA, "2026-02-06"),
    Migration("add_push_subscriptions", SCHEMA, "2026-02-18"),
    Migration("add_pgvector", SCHEMA, "2026-02-22"),
    Migration("add_waste_schedule", SCHEMA, "2026-02-26", "tabela + jednorazowe wypełnienie harmonogramem"),
    Migration("add_anonymous_chat_usage", SCHEMA, "2026-03-04"),
    Migration("add_local_places", SCHEMA, "2026-03-10"),
    Migration("add_health_tables", SCHEMA, "2026-03-16"),
    Migration("add_tsvector_bm25", SCHEMA, "2026-03-17", "kolumna, indeks, trigger + uzupełnienie istniejących wierszy"),
    Migration("add_bus_timetable", SCHEMA, "2026-04-01", "tabele + jednorazowe wypełnienie rozkładem jazdy"),
    Migration("add_payments_and_referral", SCHEMA, "2026-04-07"),
    Migration("add_user_consents", SCHEMA, "2026-07-07"),
    Migration("disable_risky_sources", DATA, "2026-07-07", "wyłącza ryzykowne źródła (jednorazowo, 7.07)"),
    Migration("add_tier1_sources", DATA, "2026-07-07", "dopisuje źródła (dane; na świeżej bazie robi to seed)"),
    Migration("add_admin_and_moderation", SCHEMA, "2026-07-08", "kolumny + nadanie roli admina"),
    Migration("secure_social_snippets", DATA, "2026-07-08", "przycina treść źródeł social do wypisu (decyzja prawna, jednorazowo)"),
    Migration("add_chat_feedback", SCHEMA, "2026-07-12"),
    Migration("ceidg_minimalizacja_rodo", SCHEMA, "2026-07-12", "kolumny + jednorazowa minimalizacja danych CEIDG (RODO)"),
    Migration("add_business_profiles", SCHEMA, "2026-07-12"),
    Migration("add_business_announcements", SCHEMA, "2026-07-21"),
    Migration("add_ceidg_status_tracking", SCHEMA, "2026-07-21"),
    Migration("normalize_ceidg_casing", DATA, "2026-07-21", "normalizuje wielkość liter w adresach CEIDG (dane)"),
    Migration("ceidg_usun_kontakt_rejestrowy", DATA, "2026-07-25", "RODO: kasuje kontakt rejestrowy CEIDG (dane)"),
    Migration("add_article_display_title", SCHEMA, "2026-07-26"),
    Migration("add_article_is_promotional", SCHEMA, "2026-07-26"),
    Migration("add_article_event_window", SCHEMA, "2026-07-27", "kolumny + jednorazowe scalenie duplikatów Energi"),
    Migration("add_article_alert_pushed", SCHEMA, "2026-07-27", "kolumna + oznaczenie już wysłanych"),
    Migration("add_bip_documents", SCHEMA, "2026-08-03"),
    Migration("add_council_sessions", SCHEMA, "2026-08-09"),
    Migration("add_article_content_score", SCHEMA, "2026-08-11"),
    Migration("add_business_impressions", SCHEMA, "2026-08-12"),
    Migration("add_manual_businesses", SCHEMA, "2026-08-18"),
    Migration("add_business_claim_log", SCHEMA, "2026-08-19", "tabela + wpisy historyczne"),
    Migration("add_trial_reminder", SCHEMA, "2026-08-20"),
    Migration("add_subscription_reminder", SCHEMA, "2026-08-20"),
    Migration("add_locality_and_event_dedup", SCHEMA, "2026-08-21", "kolumny + jednorazowe oznaczenie"),
    Migration("add_agent_tool_calls", SCHEMA, "2026-08-24"),
    Migration("add_push_subscription_location", SCHEMA, "2026-08-24"),
    Migration("add_legal_acts", SCHEMA, "2026-08-24"),
    Migration("add_gmina_institutions", SCHEMA, "2026-08-24"),
    Migration("strip_apify_key_from_sources", DATA, "2026-08-24", "usuwa klucz Apify z sources.scraping_config (dane)"),
    Migration("add_site_events", SCHEMA, "2026-08-30"),
    Migration("drop_event_text_unique", SCHEMA, "2026-09-03"),
    Migration("swap_vector_index_to_hnsw", SCHEMA, "2026-09-05"),
    Migration("widen_ceidg_status", SCHEMA, "2026-09-14"),
    Migration("add_article_event_checked", SCHEMA, "2026-09-16"),
    Migration("add_gmina_fb_sources", DATA, "2026-09-16", "dopisuje 4 profile FB jako źródła (dane; na świeżej bazie robi to seed)"),
    Migration("add_user_roles_and_solectwo_posts", SCHEMA, "2026-09-27", "tabele + dopisanie źródła „RybnoLive - Sołectwa”"),
    Migration("add_source_freshness", SCHEMA, "2026-10-11"),
    Migration("add_job_runs", SCHEMA, "2026-10-11"),
    Migration("add_article_story", SCHEMA, "2026-10-11"),
    Migration("add_solectwo_post_history", SCHEMA, "2026-10-12", "tabele i kolumny + wersja 1 dla już opublikowanych"),
]

BY_NAME = {m.name: m for m in MANIFEST}
