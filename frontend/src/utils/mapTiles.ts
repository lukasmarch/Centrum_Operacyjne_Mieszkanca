/**
 * Podkład map (autobus, Zgłoszenia 24) — jedno miejsce na adres kafelków.
 *
 * Do 13.10.2026 obie mapy brały kafelki z CARTO (`basemaps.cartocdn.com`),
 * który od pewnego czasu bez klucza API oddaje zamiast mapy obrazek
 * „API KEY REQUIRED” — także dla rybnolive.pl. Mapa „ładowała się”, tylko
 * nic na niej nie było widać. OpenStreetMap działa bez klucza; licencja
 * (ODbL) wymaga widocznego podpisu, dlatego `attribution` jest obowiązkowe
 * i kontrolki podpisu nie wolno wyłączać.
 */
export const MAP_TILE_URL = 'https://tile.openstreetmap.org/{z}/{x}/{y}.png';

export const MAP_ATTRIBUTION =
    '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>';
