"""
Ocena jakości wiadomości wchodzących do feedu i briefingu.

Powstało z pytania, na które nie umieliśmy odpowiedzieć liczbą: „czy awarie
zabijają feed?". Intuicja mówiła, że tak; bez pomiaru nie dało się odróżnić
prawdziwego problemu (awaria wypycha wszystko) od wrażenia (awarii jest mało,
ale stoją na górze, więc rzucają się w oczy).

Trzy warstwy, bo to trzy różne pytania:

1. WOLUMEN     — ile materiału w ogóle wpada i skąd. Odpowiada na pytanie
                 „czy mamy z czego wybierać".
2. EKSPOZYCJA  — co mieszkaniec ZOBACZYŁ. Odtwarza feed dokładnie tą samą
                 polityką co `api/main.py` (article_score → collapse_duplicates
                 → is_pinned_alert → diversify), tylko z `now` cofniętym na
                 poranek każdego dnia. Miara: udział miejsc w pierwszej piątce,
                 nie udział we wpisach — o wrażeniu mieszkańca decyduje góra feedu.
3. JAKOŚĆ      — czym te wpisy są jako tekst: czy nazywają miejsce w gminie,
                 czy mówią coś konkretnego, czy mieszkaniec może z nimi coś
                 zrobić, jaki mają wydźwięk. Ocenia model (rubryka niżej),
                 bo „atrakcyjność tytułu" nie jest wielkością, którą da się
                 policzyć regexem.

Użycie:
    ssh -f -N -L 55432:172.18.0.2:5432 root@91.99.142.30
    cd backend && DATABASE_URL='postgresql://centrum_user:HASLO@localhost:55432/centrum_operacyjne' \\
        python -u -m scripts.analyze_feed_quality [--days 7] [--no-llm] [--json PLIK]

`--no-llm` = same warstwy 1 i 2, bez kosztów modelu.
Skrypt jest wyłącznie do czytania bazy — nie zapisuje niczego.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Optional
from zoneinfo import ZoneInfo

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from src.services.alert_policy import places_in  # noqa: E402
from src.services.feed_policy import (  # noqa: E402
    MAX_PINNED,
    article_score,
    collapse_duplicates,
    dedup_text,
    diversify,
    is_local_article,
    is_pinned_alert,
    source_label,
    source_weight,
)

LOCAL_TZ = ZoneInfo("Europe/Warsaw")

# Feed mierzymy o tej godzinie lokalnego czasu — po przebiegu 6:00/6:15, czyli
# w momencie, w którym mieszkaniec pierwszy raz w ciągu dnia otwiera stronę.
MEASURE_HOUR_LOCAL = 8

# Parametry endpointu /api/articles, których feed używa w produkcji
FEED_DAYS = 2
FEED_PER_SOURCE = 5

# Ile pozycji liczymy jako „to, co mieszkaniec faktycznie widzi"
TOP_VISIBLE = 5


@dataclass
class Art:
    """Wpis w postaci, jakiej oczekuje feed_policy (te same nazwy atrybutów)."""

    id: int
    source_id: int
    source_name: str
    title: str
    display_title: Optional[str]
    content: Optional[str]
    summary: Optional[str]
    url: str
    category: Optional[str]
    published_at: Optional[datetime]
    scraped_at: Optional[datetime]
    event_at: Optional[datetime]
    event_until: Optional[datetime]
    content_score: Optional[int]
    is_filler: bool
    is_promotional: bool
    processed: bool

    @property
    def shown_title(self) -> str:
        """Tytuł w brzmieniu, w jakim trafia na ekran."""
        return self.display_title or self.title

    @property
    def is_alert(self) -> bool:
        return bool(self.category and "awari" in self.category.lower())

    def local(self) -> bool:
        """Lokalność w rozumieniu produkcji — tak liczy dziś feed i briefing."""
        return is_local_article(self.source_name, self.title, self.content)

    def local_by_text(self) -> bool:
        """
        Lokalność sprawdzona w TREŚCI, dla każdego źródła tak samo.

        `is_local_article` czyta treść wyłącznie dla feedów Energi; dla KPP,
        Radia 7 czy profili FB wystarcza sama przynależność źródła do
        LOCAL_SOURCES. Dlatego „Zasady bezpieczeństwa na letnie wyprawy w góry"
        z KPP Działdowo liczy się w produkcji jako wpis lokalny, choć nie pada
        w nim ani jedna nazwa z gminy. Różnica między tymi dwiema miarami jest
        miarą tego, jak bardzo zawyżamy sobie lokalność.
        """
        return bool(places_in(self.shown_title, self.content))


# --- warstwa 1: wolumen ------------------------------------------------------


def fetch(conn, days: int) -> list[Art]:
    """Wszystko z okna, łącznie z odrzutami — udział odrzutów jest wynikiem."""
    cur = conn.cursor()
    cur.execute(
        """
        SELECT a.id, a.source_id, s.name, a.title, a.display_title, a.content,
               a.summary, a.url, a.category, a.published_at, a.scraped_at,
               a.event_at, a.event_until, a.content_score,
               a.is_filler, a.is_promotional, a.processed
        FROM articles a JOIN sources s ON s.id = a.source_id
        WHERE a.published_at >= now() - make_interval(days => %s)
           OR a.scraped_at   >= now() - make_interval(days => %s)
           OR a.event_until  >= now() - make_interval(days => %s)
        ORDER BY a.published_at DESC
        """,
        (days, days, days),
    )
    return [Art(*row) for row in cur.fetchall()]


def fetch_summaries(conn, days: int) -> list[dict]:
    cur = conn.cursor()
    cur.execute(
        """
        SELECT date, headline, content, generated_at
        FROM daily_summaries
        WHERE date >= now() - make_interval(days => %s)
        ORDER BY date
        """,
        (days,),
    )
    return [
        {"date": d, "headline": h, "content": c or {}, "generated_at": g}
        for d, h, c, g in cur.fetchall()
    ]


def fetch_source_health(conn) -> list[tuple]:
    cur = conn.cursor()
    cur.execute(
        """
        SELECT s.name, s.status, s.last_scraped,
               MAX(a.published_at) AS ostatni,
               COUNT(a.id) FILTER (WHERE a.published_at >= now() - interval '7 days') AS w7,
               COUNT(a.id) FILTER (WHERE a.published_at >= now() - interval '30 days') AS w30
        FROM sources s LEFT JOIN articles a ON a.source_id = s.id
        GROUP BY s.name, s.status, s.last_scraped
        ORDER BY w7 DESC, ostatni DESC NULLS LAST
        """
    )
    return cur.fetchall()


# --- warstwa 2: ekspozycja ---------------------------------------------------


def simulate_feed(articles: list[Art], now: datetime, limit: int = 50) -> list[Art]:
    """
    Feed w kształcie, w jakim zobaczyłby go mieszkaniec o godzinie `now`.

    Odtwarza `api/main.py::get_articles` krok w krok. Każde odstępstwo tutaj
    znaczy, że mierzymy coś innego niż to, co poszło na ekran, więc kolejność
    operacji jest celowo taka sama, łącznie z podwójnym sortowaniem.
    """
    cutoff = now - timedelta(days=FEED_DAYS)

    okno = [
        a
        for a in articles
        if not a.is_filler
        and not a.is_promotional
        and (
            (a.published_at and a.published_at >= cutoff)
            or (a.scraped_at and a.scraped_at >= cutoff)
            or (a.event_until and a.event_until >= now)
        )
        # wpis, którego jeszcze nie było na świecie, nie mógł być w feedzie
        and (a.scraped_at is None or a.scraped_at <= now)
    ]

    # limit per źródło: ROW_NUMBER() po coalesce(event_at, published_at) DESC
    per_source: dict[int, list[Art]] = defaultdict(list)
    for a in sorted(
        okno,
        key=lambda x: (x.event_at or x.published_at or datetime.min, x.scraped_at or datetime.min),
        reverse=True,
    ):
        per_source[a.source_id].append(a)
    rows = [a for group in per_source.values() for a in group[:FEED_PER_SOURCE]]

    def score(a: Art) -> float:
        return article_score(
            a.published_at, a.scraped_at, a.source_name, now, a.event_at, a.event_until,
            a.content_score,
        )

    rows.sort(key=score, reverse=True)
    rows = collapse_duplicates(rows, text_of=dedup_text)

    pinned, regular = [], []
    for a in rows:
        bucket = (
            pinned
            if is_pinned_alert(
                a.category, a.published_at, a.scraped_at, now,
                a.event_at, a.event_until, a.title, a.content,
            )
            else regular
        )
        bucket.append(a)

    overflow, pinned = pinned[MAX_PINNED:], pinned[:MAX_PINNED]
    regular = sorted(regular + overflow, key=score, reverse=True)

    pinned = diversify(pinned, key=lambda a: a.source_id)
    ordered = pinned + diversify(regular, key=lambda a: a.source_id, preceding=pinned)
    return ordered[:limit]


def morning(day: datetime.date) -> datetime:
    """Naiwny UTC odpowiadający `MEASURE_HOUR_LOCAL` czasu lokalnego danego dnia."""
    local = datetime.combine(day, datetime.min.time(), LOCAL_TZ).replace(
        hour=MEASURE_HOUR_LOCAL
    )
    return local.astimezone(ZoneInfo("UTC")).replace(tzinfo=None)


# --- warstwa 3: jakość -------------------------------------------------------

RUBRYKA = """Oceniasz TYTUŁY wiadomości w serwisie lokalnym dla mieszkańców gminy Rybno
(powiat działdowski, warmińsko-mazurskie, ~4 tys. mieszkańców). Serwis konkuruje
o uwagę z lokalnymi grupami na Facebooku.

Dla KAŻDEGO wpisu zwróć obiekt:
- id: liczba (przepisz)
- lokalnosc: 0-3. 3 = nazywa miejscowość z gminy Rybno (Rybno, Koszelewy, Żabiny,
  Groszki, Naguszewo, Dębień, Truszczyny, Hartowiec, Gronowo, Jeglia, Kopaniarze,
  Wery, Grabacz, Szczupliny, Prusy, Rumian, Tuczki, Wlewsk, Wąpiersk, Świnie Górne).
  2 = powiat działdowski (Działdowo, Lidzbark, Płośnica, Iłowo). 1 = województwo.
  0 = bez związku z regionem.
- konkret: 0-3. Czy tytuł mówi CO się stało — fakt, liczba, termin, nazwa?
  0 = ogólnik ("Ważne informacje"), 3 = "Wyłączenie prądu w Kopaniarzach 11.08, 9-14".
- uzytecznosc: 0-3. Czy mieszkaniec może z tym coś ZROBIĆ (przyjść, załatwić,
  przygotować się, uniknąć)? 0 = tylko do wiadomości, 3 = wymaga działania w tym tygodniu.
- przyciaganie: 0-3. Czy chce się to kliknąć? Oceniaj uczciwie: sucha formuła
  urzędowa i setny komunikat o wyłączeniu prądu to 0-1, nawet jeśli są użyteczne.
- wydzwiek: -2..2. -2 = tragedia/śmierć, -1 = kłopot/awaria/przestępstwo,
  0 = neutralne, 1 = pozytywne, 2 = powód do dumy/radości.
- temat: jedno z: awaria, przestepczosc, wypadek, urzad, inwestycja, kultura,
  sport, edukacja, zdrowie, ludzie, biznes, ogloszenie, inne
- powtarzalny: true/false — czy to kolejna sztuka tej samej serii komunikatów
  (wyłączenia prądu, kroniki policyjne), którą stały czytelnik zna na pamięć
- uwaga: maksymalnie 12 słów po polsku — co jest z tym tytułem nie tak, albo "ok"

Zwróć WYŁĄCZNIE tablicę JSON, bez komentarza."""


def evaluate_titles(items: list[Art], model: str = "gpt-4o") -> dict[int, dict]:
    """Ocena rubryką. Partiami, bo długi JSON model potrafi urwać w połowie."""
    from openai import OpenAI

    client = OpenAI()
    out: dict[int, dict] = {}
    BATCH = 12

    for start in range(0, len(items), BATCH):
        chunk = items[start : start + BATCH]
        payload = [
            {
                "id": a.id,
                "tytul": a.shown_title,
                "kategoria": a.category,
                "zrodlo": source_label(a.source_name) or "profil lokalny",
                "fragment": (a.content or a.summary or "")[:200],
            }
            for a in chunk
        ]
        resp = client.chat.completions.create(
            model=model,
            temperature=0,
            response_format={"type": "json_object"},
            messages=[
                {"role": "system", "content": RUBRYKA},
                {
                    "role": "user",
                    "content": "Oceń wpisy. Zwróć {\"oceny\": [...]}\n\n"
                    + json.dumps(payload, ensure_ascii=False, default=str),
                },
            ],
        )
        try:
            data = json.loads(resp.choices[0].message.content)
            for row in data.get("oceny", data if isinstance(data, list) else []):
                out[int(row["id"])] = row
        except (json.JSONDecodeError, KeyError, TypeError) as exc:
            print(f"  ⚠️  partia {start}: {exc}", file=sys.stderr)
        print(f"  oceniono {min(start + BATCH, len(items))}/{len(items)}", flush=True)

    return out


# --- raport ------------------------------------------------------------------


def bar(n: int, total: int, width: int = 28) -> str:
    if not total:
        return ""
    filled = round(width * n / total)
    return "█" * filled + "·" * (width - filled)


def pct(n: int, total: int) -> str:
    return f"{100 * n / total:5.1f}%" if total else "    —"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--days", type=int, default=7)
    ap.add_argument("--no-llm", action="store_true")
    ap.add_argument("--model", default="gpt-4o")
    ap.add_argument("--json", help="zapisz surowe wyniki do pliku")
    args = ap.parse_args()

    import psycopg2

    dsn = os.environ.get("DATABASE_URL")
    if not dsn:
        print("Brak DATABASE_URL", file=sys.stderr)
        return 2
    conn = psycopg2.connect(dsn.replace("postgresql+asyncpg://", "postgresql://"))

    articles = fetch(conn, args.days)
    summaries = fetch_summaries(conn, args.days)
    health = fetch_source_health(conn)
    now = datetime.utcnow()
    okno_dni = sorted({a.published_at.date() for a in articles if a.published_at})

    W = 78
    print("=" * W)
    print(f"OCENA JAKOŚCI FEEDU — {args.days} dni do {now:%Y-%m-%d %H:%M} UTC".center(W))
    print("=" * W)

    # ---- 1. WOLUMEN
    publishable = [a for a in articles if not a.is_filler and not a.is_promotional]
    odrzuty = len(articles) - len(publishable)
    print(f"\n▌1. WOLUMEN\n")
    print(f"  Pobrano wpisów:        {len(articles)}")
    print(f"  Odrzucono (filler/reklama): {odrzuty}  ({pct(odrzuty, len(articles))})")
    print(f"  Do pokazania:          {len(publishable)}")
    print(f"  Aktywnych źródeł:      {len({a.source_id for a in articles})}")
    print(f"  Średnio na dobę:       {len(publishable) / max(len(okno_dni), 1):.1f}")

    print(f"\n  Wpisy wg źródła (waga w rankingu):")
    per_src = Counter(a.source_name for a in publishable)
    for name, n in per_src.most_common():
        lokal = sum(1 for a in publishable if a.source_name == name and a.local())
        print(
            f"    {bar(n, len(publishable))} {n:3}  {pct(n, len(publishable))}  "
            f"w={source_weight(name):.2f}  lok={lokal:2}/{n:<2} {name}"
        )

    print(f"\n  Zdrowie źródeł (cisza = scraper żyje, ale nic nie przynosi):")
    for name, status, last_scraped, ostatni, w7, w30 in health:
        cisza = (now - ostatni).days if ostatni else None
        flaga = "🔴" if (cisza is None or cisza > 7) and status == "active" else (
            "🟡" if cisza and cisza > 3 else "🟢"
        )
        if status != "active":
            flaga = "⚫"
        ost = f"{ostatni:%Y-%m-%d}" if ostatni else "nigdy"
        print(f"    {flaga} {name:<40} ost.wpis {ost}  7d={w7:<3} 30d={w30:<3} [{status}]")

    print(f"\n  Kategorie:")
    per_cat = Counter(a.category or "(brak)" for a in publishable)
    for cat, n in per_cat.most_common():
        print(f"    {bar(n, len(publishable))} {n:3}  {pct(n, len(publishable))}  {cat}")

    # ---- 2. EKSPOZYCJA
    print(f"\n\n▌2. EKSPOZYCJA — co mieszkaniec widział rano ({MEASURE_HOUR_LOCAL}:00)\n")
    print(f"  Feed odtworzony polityką produkcyjną (per_source={FEED_PER_SOURCE}, days={FEED_DAYS}).")
    print(f"  Liczy się pierwsza {TOP_VISIBLE}-ka: tyle widać bez przewijania.\n")

    slots_top: Counter = Counter()
    slots_cat: Counter = Counter()
    alert_slots = 0
    local_slots = 0
    local_text_slots = 0
    total_slots = 0
    dzienne: list[dict] = []
    poprzedni_ids: set[int] = set()
    powtorki_total = 0
    porownan = 0

    for day in okno_dni:
        moment = morning(day)
        if moment > now:
            continue
        feed = simulate_feed(articles, moment)
        top = feed[:TOP_VISIBLE]
        if not top:
            continue
        for a in top:
            slots_top[a.source_name] += 1
            slots_cat[a.category or "(brak)"] += 1
            alert_slots += a.is_alert
            local_slots += a.local()
            local_text_slots += a.local_by_text()
            total_slots += 1

        ids = {a.id for a in top}
        powtorki = len(ids & poprzedni_ids) if poprzedni_ids else 0
        if poprzedni_ids:
            powtorki_total += powtorki
            porownan += len(top)

        dzienne.append(
            {
                "dzien": str(day),
                "awarie_w_top5": sum(1 for a in top if a.is_alert),
                "lokalne_w_top5": sum(1 for a in top if a.local()),
                "lokalne_trescia": sum(1 for a in top if a.local_by_text()),
                "powtorki_z_wczoraj": powtorki,
                "pozycje": [
                    {
                        "poz": i + 1,
                        "id": a.id,
                        "tytul": a.shown_title[:64],
                        "zrodlo": source_label(a.source_name) or a.source_name,
                        "kat": a.category,
                        "lok": a.local(),
                        "lok_tresc": a.local_by_text(),
                        "wczoraj": a.id in poprzedni_ids,
                    }
                    for i, a in enumerate(top)
                ],
            }
        )
        poprzedni_ids = ids

    print(f"  Zmierzonych miejsc w pierwszej piątce: {total_slots}")
    print(f"  Zajętych przez AWARIE:   {alert_slots:3}  {pct(alert_slots, total_slots)}")
    print(f"\n  Lokalność — dwie miary tego samego:")
    print(f"    wg produkcji (źródło z listy):  {local_slots:3}  {pct(local_slots, total_slots)}")
    print(f"    wg treści (pada nazwa z gminy): {local_text_slots:3}  {pct(local_text_slots, total_slots)}")
    print(f"    ⚠️  różnica = {local_slots - local_text_slots} miejsc, które liczymy jako lokalne,")
    print(f"        choć nie pada w nich żadna nazwa z gminy Rybno")
    print(f"\n  Powtórki: {powtorki_total}/{porownan} miejsc {pct(powtorki_total, porownan)} zajmuje wpis,")
    print(f"    który stał w pierwszej piątce już poprzedniego dnia")

    print(f"\n  Kto zajmuje pierwszą piątkę:")
    for name, n in slots_top.most_common():
        print(f"    {bar(n, total_slots)} {n:3}  {pct(n, total_slots)}  {source_label(name) or name}")

    print(f"\n  Czym jest pierwsza piątka:")
    for cat, n in slots_cat.most_common():
        print(f"    {bar(n, total_slots)} {n:3}  {pct(n, total_slots)}  {cat}")

    print(f"\n  Dzień po dniu   (⚡awaria  📍nazwa z gminy w treści  ↺wczoraj też tu stało):")
    for d in dzienne:
        print(
            f"\n    ── {d['dzien']}   awarie {d['awarie_w_top5']}/5, "
            f"lokalne treścią {d['lokalne_trescia']}/5, powtórki {d['powtorki_z_wczoraj']}/5"
        )
        for p in d["pozycje"]:
            znak = "⚡" if p["kat"] and "awari" in (p["kat"] or "").lower() else ("📍" if p["lok_tresc"] else "  ")
            powt = "↺" if p["wczoraj"] else " "
            print(f"       {p['poz']}.{powt}{znak} {p['tytul']:<64} [{p['zrodlo']}]")

    # ---- 3. BRIEFING
    print(f"\n\n▌3. BRIEFING DNIA\n")
    naglowki_awarie = 0
    for s in summaries:
        cited = s["content"].get("cited_articles") or []
        head_src = cited[0].get("source_name", "?") if cited else "—"
        awaria = "⚡" if "AWARIA" in s["headline"].upper() else "  "
        naglowki_awarie += awaria == "⚡"
        print(f"  {s['date']:%m-%d} {awaria} {s['headline'][:70]}")
        print(f"          źródło nagłówka: {head_src}, cytowanych: {len(cited)}")
    print(f"\n  Nagłówków o awarii: {naglowki_awarie}/{len(summaries)}  {pct(naglowki_awarie, len(summaries))}")

    # ---- 4. JAKOŚĆ
    oceny: dict[int, dict] = {}
    if not args.no_llm:
        print(f"\n\n▌4. JAKOŚĆ TYTUŁÓW (model {args.model})\n")
        widziane = {a.id: a for d in dzienne for p in d["pozycje"] for a in [next(x for x in articles if x.id == p["id"])]}
        do_oceny = list({a.id: a for a in list(widziane.values()) + publishable}.values())
        print(f"  Oceniam {len(do_oceny)} tytułów…")
        oceny = evaluate_titles(do_oceny, args.model)

        if oceny:
            wymiary = ["lokalnosc", "konkret", "uzytecznosc", "przyciaganie"]
            print(f"\n  Średnie (0-3) — wszystkie wpisy vs. te, które weszły do pierwszej piątki:")
            widziane_ids = set(widziane)
            for w in wymiary:
                vals = [o.get(w, 0) for o in oceny.values() if isinstance(o.get(w), (int, float))]
                vis = [
                    o.get(w, 0)
                    for i, o in oceny.items()
                    if i in widziane_ids and isinstance(o.get(w), (int, float))
                ]
                sa = sum(vals) / len(vals) if vals else 0
                sv = sum(vis) / len(vis) if vis else 0
                print(f"    {w:<14} wszystkie {sa:.2f}   w top5 {sv:.2f}   {'▲' if sv > sa else '▼'}")

            wyd = [o.get("wydzwiek", 0) for o in oceny.values() if isinstance(o.get("wydzwiek"), (int, float))]
            wyd_vis = [
                o.get("wydzwiek", 0)
                for i, o in oceny.items()
                if i in widziane_ids and isinstance(o.get("wydzwiek"), (int, float))
            ]
            print(f"\n  Wydźwięk (-2..+2): wszystkie {sum(wyd)/max(len(wyd),1):+.2f}, "
                  f"w pierwszej piątce {sum(wyd_vis)/max(len(wyd_vis),1):+.2f}")
            neg = sum(1 for v in wyd_vis if v < 0)
            print(f"  Negatywnych w pierwszej piątce: {neg}/{len(wyd_vis)}  {pct(neg, len(wyd_vis))}")

            print(f"\n  Tematy:")
            for t, n in Counter(o.get("temat", "?") for o in oceny.values()).most_common():
                print(f"    {bar(n, len(oceny))} {n:3}  {pct(n, len(oceny))}  {t}")

            powt = sum(1 for o in oceny.values() if o.get("powtarzalny"))
            print(f"\n  Wpisy z serii, którą czytelnik zna na pamięć: {powt}/{len(oceny)}  {pct(powt, len(oceny))}")

            print(f"\n  Najsłabsze tytuły w pierwszej piątce (suma wymiarów):")
            ranked = sorted(
                [(sum(o.get(w, 0) for w in wymiary), i, o) for i, o in oceny.items() if i in widziane_ids]
            )
            for total, i, o in ranked[:10]:
                art = widziane[i]
                print(f"    [{total:2}/12] {art.shown_title[:58]:<58} — {o.get('uwaga','')}")

            print(f"\n  Najlepsze tytuły w całym materiale:")
            best = sorted(
                [(sum(o.get(w, 0) for w in wymiary), i, o) for i, o in oceny.items()], reverse=True
            )
            by_id = {a.id: a for a in articles}
            for total, i, o in best[:8]:
                art = by_id.get(i)
                widz = "✓w top5" if i in widziane_ids else "✗niewidoczny"
                if art:
                    print(f"    [{total:2}/12] {widz:<12} {art.shown_title[:52]}")

    if args.json:
        with open(args.json, "w", encoding="utf-8") as fh:
            json.dump(
                {
                    "wygenerowano": now.isoformat(),
                    "dni": args.days,
                    "wpisy": [
                        {
                            "id": a.id, "tytul": a.shown_title, "zrodlo": a.source_name,
                            "kategoria": a.category, "lokalny": a.local(),
                            "published_at": a.published_at.isoformat() if a.published_at else None,
                            "event_at": a.event_at.isoformat() if a.event_at else None,
                            "filler": a.is_filler, "promo": a.is_promotional,
                            "ocena": oceny.get(a.id),
                        }
                        for a in articles
                    ],
                    "ekspozycja": dzienne,
                    "briefingi": [
                        {"date": str(s["date"]), "headline": s["headline"]} for s in summaries
                    ],
                },
                fh,
                ensure_ascii=False,
                indent=2,
            )
        print(f"\n  → surowe dane: {args.json}")

    print("\n" + "=" * W)
    return 0


if __name__ == "__main__":
    sys.exit(main())
