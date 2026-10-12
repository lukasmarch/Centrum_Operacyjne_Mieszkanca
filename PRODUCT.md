# Product

<!-- impeccable:product-schema 1 -->

## Platform

web

(PWA: instalowalna, z powiadomieniami push. Brak aplikacji natywnej.)

## Users

**Główny użytkownik — rozstrzyga, gdy interesy się kłócą:** dorosły mieszkaniec gminy Rybno
(powiat działdowski) na telefonie. Wchodzi z posta na Facebooku albo z powiadomienia push
i chce w kilka sekund wiedzieć: czy jest awaria w mojej wsi, kiedy wywóz, co dziś
i jutro dzieje się w gminie.

Warstwy nad mieszkańcem (ważne, ale podporządkowane):
- **Abonent Premium** — ten sam mieszkaniec, który płaci za briefing dzienny, push, asystenta bez limitu.
- **Sołtys** — rola z zakresem jednego sołectwa; publikuje ogłoszenia ze zdjęcia pisma, przez moderację.
- **Firma lokalna** — plan „Firma lokalna" (B2B), wyróżniona wizytówka w katalogu.
- **Redakcja / admin** — moderacja zgłoszeń, ogłoszeń sołectw, akceptacja skrótów sesji Rady.

## Product Purpose

RybnoLive (rybnolive.pl, hasło „Twoja gmina. Na żywo.") zbiera w jednym miejscu wszystko,
co dotyczy gminy Rybno: wiadomości, awarie prądu i wody, wydarzenia, wywóz odpadów,
pogodę i powietrze, autobusy, kino, sesje Rady, uchwały, statystyki GUS i katalog firm —
oraz asystenta AI, który odpowiada z tych danych.

Sukces: mieszkaniec dowiaduje się o sprawie swojej wsi tu, a nie przypadkiem; zakłada konto,
włącza push, wraca. Dziś wąskim gardłem nie jest zasięg na Facebooku, tylko przejście
z zasięgu do konta i zgody push.

## Positioning

- **Hiperlokalność z bramką miejsca.** Pokazujemy to, co dotyczy gminy Rybno i konkretnej wsi;
  kod odsiewa sąsiednie gminy (Płośnica, Działdowo, Mława), nawet gdy źródło jest powiatowe.
- **Jedno miejsce zamiast kilkunastu źródeł.** Energa, ZGK, BIP, Facebook gminy i sołectw,
  media powiatowe, GUS, harmonogram odpadów, rozkłady — zebrane i zdeduplikowane.
- **Asystent AI na danych gminy.** Agenci (Redaktor, Urzędnik, Strażnik, Przewodnik,
  Organizator, GUS-Analityk, Koordynator) odpowiadają z bazy i podają źródło.

## Operating Context

- Ruch przychodzi głównie z Facebooka (fanpage, rolki, posty ze zdjęciem z deep linkiem
  do konkretnej sekcji) i z powiadomień push; wejścia są mobilne.
- Rytm dnia: briefing dzienny (strona + mail Premium 7:15), alerty awarii co 15 min,
  wieczorne przypomnienie o wywozie (18:00), newsletter tygodniowy w sobotę.
- Treść powstaje automatycznie (scraping → kategoryzacja AI → ranking), część przechodzi
  przez ręczną akceptację (sesje Rady, ogłoszenia sołtysów, Zgłoszenia 24).
- Nawigacja to sekcje jednej aplikacji (pulpit, wiadomości, wydarzenia, odpady, autobusy,
  kino, sesje, pogoda, statystyki, firmy, zgłoszenia, asystent, premium, strony prawne).

## Capabilities and Constraints

- Plany: Dla Każdego (0 zł; alerty push o awariach, 5 pytań AI/dzień, anonim 3, 8 wskaźników GUS),
  Premium (9,99 zł/mc · 84 zł/rok; trial 30 dni bez karty; 37 wskaźników), Firma lokalna
  (49 zł/mc · 490 zł/rok; 53 wskaźniki + wizytówka). Płatności Przelewy24; plan nie odnawia się sam.
- Każda obietnica oferty musi mieć pokrycie w kodzie (patrz CLAUDE.md, „Obietnice oferty a kod").
- Cytaty z cudzych źródeł: wypis do 300 znaków (decyzja prawna) — pełna treść jest u źródła.
- Push wymaga zgody przeglądarki; można zawęzić do wsi.
- Terminologia: 20 sołectw ≠ 22 miejscowości ≠ 24 pozycje harmonogramu odpadów — nie zamieniać.
- Czas zawsze liczony i pokazywany lokalnie, względem „teraz" („dziś 09:00–14:00 — trwa teraz", „już po").

## Brand Commitments

- Nazwa `RybnoLive` (camel case, bez spacji), domena `rybnolive.pl`, hasło „Twoja gmina. Na żywo."
- Język: polski, rzeczowy, konkretny — nazwa wsi, godzina, termin. Bez żargonu urzędowego tam,
  gdzie mieszkaniec go nie używa.
- Istniejący brand kit: `DESIGN/BRAND.md` i `DESIGN/DESIGN.md` (stan obecnego interfejsu).
- Obsada postaci w materiałach social (Kuba, Ola, Bartek): `DESIGN/OBSADA.md`.

## Evidence on Hand

- Realne dane gminy na żywo: feed, awarie, kalendarz, uchwały (430 aktów 2024–2026), sesje Rady, GUS.
- Pomiar ruchu: `site_events` (`scripts/site_report`), Windsor (fanpage), log Caddy.
- **Brak** opinii klientów, testimoniali, case studies, liczby użytkowników do chwalenia się —
  nie wolno ich wymyślać. Użytkowników jest dziś niewielu (pojedyncze konta, kilka subskrypcji push).

## Product Principles

1. **Najpierw sprawa mieszkańca w jego wsi, teraz.** Lokalność i bliskość w czasie wygrywają z nowością i ozdobą.
2. **Prawda albo nic.** Każda informacja ma źródło i termin; czego nie wiemy, mówimy wprost albo nie piszemy wcale —
   brak danych nie jest treścią dla mieszkańca.
3. **Każda obietnica ma pokrycie.** Oferta, mail, przycisk obiecują tylko to, co kod faktycznie dowozi.
4. **Link prowadzi tam, co obiecał.** Wejście z posta czy pusha ląduje w konkretnej sprawie, nie na ogólnym pulpicie.
5. **Dane osobowe minimalnie.** Nie zbieramy tego, czego nie używamy; nazwiska i telefony tylko tam, gdzie wymaga prawo.
