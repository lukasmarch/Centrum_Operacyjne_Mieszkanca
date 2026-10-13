-- Dane startowe dla bazy testowej w CI (audyt E5, etap 2). Ładowane PO prod_schema.sql.
--
-- Zasada: MINIMUM, którego wymagają testy z CI — nic z produkcyjnych danych osobowych
-- (rejestr CEIDG, konta, subskrypcje), nic zależnego od daty (harmonogram odpadów kończy się 31.12.2026,
-- więc test_waste_reminder zostaje poza CI). Nowy test potrzebuje wiersza → dopisz go TU, z powodem.
--
-- Źródło „Sołectwa”: test_solectwa publikuje ogłoszenie jako artykuł z tego źródła; na prodzie powstaje
-- migracją add_user_roles_and_solectwo_posts (rodzaj `data` w mieszanym skrypcie).
-- pg_dump zaczyna zrzut od `set_config('search_path', '', false)`; gdy psql ładuje oba pliki w jednej
-- sesji (CI), gołe `sources` przestaje być widoczne. Przywracamy ścieżkę wyszukiwania.
SET search_path TO public;

INSERT INTO sources (id, name, type, url, scraping_config, status, created_at)
VALUES (26, 'RybnoLive - Sołectwa', 'community', NULL, NULL, 'disabled', now());

-- Sekwencje ruszają powyżej ręcznie wstawionych id
SELECT setval(pg_get_serial_sequence('sources', 'id'), 1000);
