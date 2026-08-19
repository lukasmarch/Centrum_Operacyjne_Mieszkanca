"""
Treść postów na social media — jedno miejsce, w którym powstaje to, co idzie na Facebooka.

Wcześniej logika żyła w node'ach Code w n8n, zduplikowana w dwóch workflow (A budował
propozycję na Telegram, B budował ją PONOWNIE przy publikacji) — więc opublikowany post
nie musiał być tym, co zaakceptowałeś. Teraz n8n dostaje gotowy `message` i nie zna się
na treści: jest tylko cronem, przyciskiem akceptacji i wywołaniem Graph API.

Trzy rodzaje materiału:
  • text     — codzienne podsumowanie AI (z DailySummary)
  • photo    — post z grafiką generowaną w kie.ai (ilustracja + krótki claim)
  • campaign — sztywny kalendarz kampanii „Twoja gmina. Na żywo.” (27.07–10.08.2026)
"""
import asyncio
import json
import logging
import re
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional

import httpx
import openai

from src.config import settings

logger = logging.getLogger(__name__)

SITE_URL = "https://rybnolive.pl"
HASHTAGS = "#Rybno #GminaRybno #PowiatDziałdowski"

# ──────────────────────────────────────────────────────────────────────────────
# Post tekstowy (dzienne podsumowanie AI)
# ──────────────────────────────────────────────────────────────────────────────

def _clean(text: str) -> str:
    """Usuń markdownowe pogrubienia (FB ich nie renderuje) i prefiks AWARIA:."""
    return re.sub(r"\*\*", "", text or "").replace("AWARIA:", "").strip()


def build_text_post(summary: dict) -> dict:
    """
    Zbuduj post tekstowy z dziennego podsumowania.

    Kształt zachowany 1:1 z node'em Code z workflow A/B, żeby styl postów nie zmienił
    się w dniu premiery.
    """
    content = summary.get("content") or {}
    headline = _clean(content.get("headline") or summary.get("headline") or "")
    highlights = _clean(content.get("highlights") or "")
    events = [f"📅 {e}" for e in (content.get("upcoming_events") or [])[:3]]

    parts = [f"{headline}\n\n{highlights}".strip()]
    if events:
        parts.append("Nadchodzące wydarzenia:\n" + "\n".join(events))
    parts.append(f"👉 Więcej na {SITE_URL}\n{HASHTAGS}")

    return {
        "kind": "text",
        "message": "\n\n".join(p for p in parts if p),
        "headline": headline,
        "date": content.get("date") or summary.get("date"),
    }


# ──────────────────────────────────────────────────────────────────────────────
# Post graficzny (kie.ai)
# ──────────────────────────────────────────────────────────────────────────────

# Stały blok stylu — trzyma grafiki w jednej estetyce marki. Zmiana tutaj zmienia
# wszystkie przyszłe grafiki, bez klikania po n8n.
#
# Model NIE pisze na grafice ani jednej litery: claim i stopkę nakłada u nas
# social_card.compose_photo_card, naszym fontem i naszymi kolorami. Wcześniej tekst
# wypalał model — stąd pocięte wyrazy („SPADK NIKÓW MIESZKAŃCÓW”), gubione ogonki
# i inny krój w każdym poście. Powtarzalność marki zaczyna się od tego podziału.
#
# Styl (2026-08-03): naklejka komiksowa zamiast płaskiej ilustracji. Poprzedni blok
# („flat cartoon, rounded shapes, rural Masurian setting”) w połączeniu z paletą
# ograniczoną do granatu i błękitu dawał obrazki bez wyrazu — w feedzie FB, gdzie
# post ma pół sekundy na zatrzymanie kciuka, przezroczyste. Teraz: postać wycięta
# grubym białym konturem, za nią energiczne pociągnięcia pędzla, akcenty w żółci,
# magencie i fiolecie. Granat #05080f i błękit #3a81f6 zostają, więc W2 dalej czyta
# się jako ta sama seria co codzienna karta dnia z W1.
BRAND_STYLE = (
    "Bold western cartoon sticker illustration (comic/graffiti poster energy, NOT anime, "
    "not photorealistic, not 3D render): thick clean black lineart, flat cel shading with "
    "one crisp highlight, expressive slightly caricatured face, confident hand-drawn feel. "
    "The people are cut out from the background by a THICK WHITE STICKER OUTLINE. "
    "Background: near-black (#05080f) covered with energetic dry-brush paint strokes — "
    "electric blue (#3a81f6) as the dominant stroke, plus a flat warm-yellow disc, "
    "magenta dots and violet zig-zag accents scattered around the figure. "
    "Vibrant saturated colors, high contrast, poster-like composition. "
    # „Polish village” bez tego doprecyzowania model czytał jako skansen: chałupy
    # z bali i strzechy. Mieszkaniec Rybna ma się w kadrze rozpoznać, a nie poczuć,
    # że się z niego nabijamy — ta sama zasada co przy bohaterach filmów kampanii.
    "Setting is a MODERN Polish village in Masuria: plastered and brick houses with "
    "tidy gardens, contemporary cars, ordinary present-day clothes. "
    "NEVER log cabins, thatched roofs, folk costumes or rustic-poverty clichés. "
    "Keep the lower third of the frame calm and uncluttered — a headline goes there. "
    "ABSOLUTELY NO text, letters, numbers, signage, captions, logos or watermarks. "
    # Osobno o ubraniach: przy samym „no logos” model i tak wyhaftował Bartkowi
    # logo Carhartt na kieszeni — a to cudzy znak towarowy na materiale, który
    # publikujemy na fanpage'u.
    "All clothing is plain and unbranded — no brand marks, badges or prints on garments. "
    "No glowing orb, no globe, no giant hand."
)

# ── Obsada: trzy stałe twarze ────────────────────────────────────────────────
#
# Do tej pory każda grafika wymyślała ludzi od zera, więc seria nie istniała — dwa
# posty obok siebie wyglądały jak z dwóch różnych marek. Trzy powracające postacie
# robią z fanpage'a ciąg dalszy: mieszkaniec rozpoznaje Olę, zanim przeczyta nagłówek.
#
# `look` idzie do modelu graficznego dosłownie i MUSI zostać niezmieniony — to on,
# razem z arkuszem referencyjnym (assets/social/cast/), trzyma twarz w ryzach.
# `kiedy` czyta gpt-4o przy wyborze postaci do zdarzenia dnia.
CAST_ASSET_DIR = Path(__file__).parent.parent.parent / "assets" / "social" / "cast"

CAST: dict[str, dict] = {
    "kuba": {
        "name": "Kuba",
        "look": (
            "KUBA, a 26-year-old white man with warm auburn hair styled up in a short quiff "
            "with one shaved temple, round black glasses, a small black ear stud, thick "
            "expressive eyebrows, a slight knowing smirk, wearing an open orange-and-brown "
            "plaid flannel shirt over a mint-green t-shirt"
        ),
        "kiedy": "sprawdza, dopytuje, siedzi w telefonie — urząd, dane, informacje, ciekawostki, technologia",
    },
    "ola": {
        "name": "Ola",
        "look": (
            "OLA, a woman in her late twenties with dark-blonde hair in a high ponytail "
            "with a blunt fringe, light freckles across her nose, small gold hoop earrings, "
            "an open friendly expression, wearing an unzipped sunny-yellow windbreaker "
            "over a white t-shirt"
        ),
        "kiedy": "jest w środku wydarzeń — festyny, wydarzenia, weekend, sport, dobre wiadomości, ludzie",
    },
    "bartek": {
        "name": "Bartek",
        "look": (
            "BARTEK, a 30-year-old white man with a short dark beard, a charcoal knitted "
            "beanie, calm heavy-lidded eyes, broad shoulders, wearing a navy hoodie under "
            "an unzipped violet work jacket"
        ),
        "kiedy": "ogarnia sprawy praktyczne — awarie, prąd, woda, drogi, odpady, pogoda, ostrzeżenia",
    },
}

DEFAULT_CAST = "ola"


def cast_member(cast_id: Optional[str]) -> tuple[str, dict]:
    """Postać z obsady po id — z twardym fallbackiem, bo id podaje model."""
    key = (cast_id or "").strip().lower()
    if key not in CAST:
        if key:
            logger.warning(f"[social] Nieznana postać „{key}” — biorę {DEFAULT_CAST}")
        key = DEFAULT_CAST
    return key, CAST[key]


def cast_reference_path(cast_id: str) -> Path:
    """
    Plik arkusza postaci w repo — jedno miejsce, w którym żyje ta ścieżka.

    Generator (scripts/build_social_cast.py) i endpoint publikujący arkusz muszą
    zgadzać się co do nazwy i rozszerzenia; rozjazd oznacza cichy brak referencji,
    bo brakujący arkusz z założenia nie przerywa generowania posta.
    """
    return CAST_ASSET_DIR / f"{cast_id}.jpg"


def cast_sheet_prompt(cast_id: str) -> str:
    """
    Prompt arkusza referencyjnego (scripts/build_social_cast.py).

    Arkusz powstaje z TEGO SAMEGO bloku stylu co grafiki dnia — inaczej referencja
    ciągnęłaby model w stronę estetyki, której potem nie odtwarzamy.
    """
    _, member = cast_member(cast_id)
    return (
        f"Character reference sheet of one single character: {member['look']}. "
        "Two views of the SAME person side by side on one image: a large waist-up "
        "three-quarter view on the left, and a smaller head-and-shoulders close-up on the "
        "right. Neutral friendly expression, arms relaxed, full head visible with margin. "
        # Arkusz to referencja CZŁOWIEKA, nie kadru. Przy tle ze scenerią model brał
        # z niego również otoczenie i każdy post dnia dostawał te same budynki.
        "The two figures float on a COMPLETELY EMPTY dark background with only paint "
        "strokes and accents around them — no buildings, no houses, no street, no "
        "landscape, no props, not even in the corners. "
        f"{BRAND_STYLE}"
    )

CLAIM_SYSTEM_PROMPT = """Jesteś dyrektorem kreatywnym lokalnego serwisu informacyjnego RybnoLive (gmina Rybno, powiat działdowski).
Na podstawie podsumowania dnia przygotuj materiał do grafiki na Facebooka.

Zwróć WYŁĄCZNIE JSON:
{
  "claim": "hasło na grafikę: 2-4 PEŁNE wyrazy, DRUKOWANYMI literami, bez kropki na końcu",
  "cast": "kuba | ola | bartek — kto z obsady pasuje do tego zdarzenia",
  "scene": "scena po ANGIELSKU dla modelu graficznego: CO ta osoba robi, 1-2 zdania, bez tekstu na obrazku",
  "caption": "treść posta na Facebooka po polsku: 2-3 zdania, konkretnie o tym co się stało, bez hashtagów i bez linku"
}

OBSADA — trzy stałe postacie serii, w każdym poście występuje DOKŁADNIE JEDNA:
- "kuba" — sprawdza, dopytuje, siedzi w telefonie: urząd, dane, informacje, ciekawostki, technologia
- "ola" — jest w środku wydarzeń: festyny, wydarzenia, weekend, sport, dobre wiadomości, ludzie
- "bartek" — ogarnia sprawy praktyczne: awarie, prąd, woda, drogi, odpady, pogoda, ostrzeżenia
Wyglądu postaci NIE opisuj — dopisujemy go sami. W "scene" pisz o niej „he” / „she”.

ZASADY DLA claim — to nagłówek nakładany na grafikę:
- musi być poprawną polską frazą, zrozumiałą bez kontekstu
- NIGDY nie skracaj ani nie obcinaj wyrazów; każde słowo w pełnej formie
- lepiej użyć 2 słów niż 4 pocięte
- DOBRZE: "AWARIA WODY", "MNIEJ MIESZKAŃCÓW", "WEEKEND W GMINIE", "DNI RYBNA 2026"
- ŹLE: "SPADK NIKÓW MIESZKAŃCÓW" (pocięte wyrazy), "FACT-CHECKING GMINA RYBNO" (żargon),
  "SPADEK LICZBY MIESZKAŃCÓW GMINY RYBNO W ROKU 2026" (za długie)

ZASADY DLA scene — grafika ma POKAZAĆ SYTUACJĘ, nie jej symbol:
- bohaterem jest wybrana postać z obsady, pokazana od pasa w górę lub w połowie figury,
  blisko widza; drugi plan (sąsiedzi, sprzęt, budynki) tylko jako tło sytuacji
- postać ZAWSZE coś robi i reaguje twarzą; sama pozująca sylwetka jest błędem
- czynność musi wynikać wprost ze zdarzenia i oddawać jego realia:
  • awaria, utrudnienie, ostrzeżenie → widać SKUTEK i reakcję
    (wyłączony prąd: świeci sobie latarką w telefonie w ciemnej kuchni;
     awaria wody: niesie kanister od beczkowozu;
     objazd: zawraca przed zamkniętą drogą, ręka na kierownicy)
  • wydarzenie, sukces, dobra wiadomość → bierze w nim CZYNNY udział
    (festyn: klaszcze w tłumie przy scenie, w dłoni wata cukrowa;
     inwestycja: ogląda nowy chodnik, kciuk w górę)
- konkret zamiast metafory: NIE "a symbol of a power outage", tylko
  "she lights a dark kitchen with her phone torch, one eyebrow raised"
- nastrój zgodny ze zdarzeniem — przy awarii spokojna powaga, nie panika ani nie zabawa
- bez tekstu, napisów, tablic i szyldów w kadrze
- dolna część kadru spokojna (tam wchodzi nagłówek)

Pozostałe zasady:
- caption pisz naturalnie, po ludzku, bez korporacyjnego żargonu
- dotyczy WYŁĄCZNIE gminy Rybno i najbliższej okolicy"""

# Transliteracja do nazw plików — bez niej claim „SPADEK LICZBY MIESZKAŃCÓW” dawał
# nieczytelną nazwę „spadek-liczby-mieszka-c-w” (polskie znaki wypadały jako myślniki).
PL_TRANSLIT = str.maketrans({
    "ą": "a", "ć": "c", "ę": "e", "ł": "l", "ń": "n", "ó": "o", "ś": "s", "ź": "z", "ż": "z",
    "Ą": "A", "Ć": "C", "Ę": "E", "Ł": "L", "Ń": "N", "Ó": "O", "Ś": "S", "Ź": "Z", "Ż": "Z",
})


def slugify_pl(value: str) -> str:
    """Nazwa pliku z polskiego tekstu — z transliteracją, nie przez wycinanie znaków."""
    return value.translate(PL_TRANSLIT)


async def build_photo_post(summary: dict) -> dict:
    """
    Z podsumowania dnia zrób: claim na grafikę, prompt graficzny i copy posta.

    Claim i scenerię układa gpt-4o-mini — ten sam model, który kategoryzuje artykuły.
    """
    content = summary.get("content") or {}
    headline = _clean(content.get("headline") or summary.get("headline") or "")
    highlights = _clean(content.get("highlights") or "")[:1500]

    client = openai.AsyncOpenAI(api_key=settings.OPENAI_API_KEY)
    response = await client.chat.completions.create(
        # gpt-4o, nie -mini: mini cięło wyrazy w claimie („SPADK NIKÓW MIESZKAŃCÓW”),
        # a claim jest wypalany na grafice, więc błąd jest nieodwracalny i widoczny.
        model="gpt-4o",
        temperature=0.4,
        response_format={"type": "json_object"},
        messages=[
            {"role": "system", "content": CLAIM_SYSTEM_PROMPT},
            {"role": "user", "content": f"Nagłówek dnia: {headline}\n\nPodsumowanie: {highlights}"},
        ],
    )
    data = json.loads(response.choices[0].message.content)

    claim = (data.get("claim") or headline[:40]).strip().upper()
    scene = (data.get("scene") or "she looks over a quiet Masurian village at golden hour").strip()
    caption = (data.get("caption") or highlights[:300]).strip()
    cast_id, member = cast_member(data.get("cast"))

    # Model dostaje wyłącznie scenę i styl — żadnego tekstu do narysowania. Claim
    # nakładamy potem sami (social_card.compose_photo_card), więc polskie znaki
    # i krój są pewne, a nie zależne od tego, co model zrozumie z liter.
    #
    # Opis postaci idzie PRZED sceną i jest powtórzony w zdaniu o referencji: samo
    # dołączenie arkusza nie wystarcza, model traktuje go wtedy jak luźną inspirację
    # i po kilku postach Kuba gubi okulary.
    prompt = (
        f"Vertical 9:16 composition. {member['look']} — {scene} "
        # Bez wyliczanki „glasses”: przy niej model dorysowywał okulary także Bartkowi,
        # który ich nie nosi — lista cech działa jak podpowiedź, nie jak filtr.
        "Keep this character's face, hair and outfit EXACTLY as in the reference image, "
        f"and add nothing they do not already wear. {BRAND_STYLE}"
    )

    # Claim NIE wchodzi do treści posta — jest już wypalony na grafice, a powtórzenie
    # wyglądałoby jak błąd. (Nie używamy tu capitalize(): psuje nazwy własne — „w rybnie”.)
    message = f"{caption}\n\n👉 {SITE_URL}\n{HASHTAGS}"

    return {
        "kind": "photo",
        "message": message,
        "claim": claim,
        "cast": cast_id,
        "prompt": prompt,
        "date": content.get("date") or summary.get("date"),
    }


# ──────────────────────────────────────────────────────────────────────────────
# kie.ai — generowanie grafiki
# ──────────────────────────────────────────────────────────────────────────────

KIE_BASE = "https://api.kie.ai/api/v1/jobs"
KIE_POLL_INTERVAL = 5.0
KIE_TIMEOUT_SECONDS = 180
MAX_REFERENCE_IMAGES = 8  # limit nano-banana-pro dla image_input


async def generate_image(
    prompt: str,
    aspect_ratio: str = "9:16",
    resolution: str = "2K",
    references: Optional[list[str]] = None,
) -> str:
    """
    Wygeneruj grafikę w kie.ai i zwróć jej (tymczasowy!) URL.

    Zwracany link żyje ~24h — dlatego wywołujący MUSI go od razu zapisać u nas
    (patrz store_image_from_url w endpoints/social.py).

    `references` to publiczne URL-e arkuszy postaci — tak trzymamy jedną twarz przez
    całą serię. Pole nazywa się `image_input` (do 8 obrazów); `image_urls` z części
    poradników dotyczy innych modeli kie.ai i tutaj zostałoby po cichu zignorowane,
    czyli referencja przestałaby działać bez jednego błędu w logu.
    """
    if not settings.KIE_API_KEY:
        raise RuntimeError("Brak KIE_API_KEY — generowanie grafik wyłączone")

    headers = {"Authorization": f"Bearer {settings.KIE_API_KEY}"}
    payload = {
        "model": settings.KIE_MODEL,
        "input": {
            "prompt": prompt,
            "image_input": (references or [])[:MAX_REFERENCE_IMAGES],
            "aspect_ratio": aspect_ratio,
            "resolution": resolution,
            "output_format": "png",
        },
    }

    async with httpx.AsyncClient(timeout=60.0) as client:
        created = await client.post(f"{KIE_BASE}/createTask", json=payload, headers=headers)
        created.raise_for_status()
        body = created.json()
        if body.get("code") != 200:
            raise RuntimeError(f"kie.ai odrzuciło zadanie: {body.get('msg')}")

        task_id = body["data"]["taskId"]
        logger.info(f"[kie.ai] Zadanie {task_id} ({settings.KIE_MODEL}) utworzone")

        deadline = datetime.now() + timedelta(seconds=KIE_TIMEOUT_SECONDS)
        while datetime.now() < deadline:
            await asyncio.sleep(KIE_POLL_INTERVAL)
            info = await client.get(f"{KIE_BASE}/recordInfo", params={"taskId": task_id}, headers=headers)
            info.raise_for_status()
            data = info.json().get("data") or {}
            state = data.get("state")

            if state == "success":
                urls = json.loads(data.get("resultJson") or "{}").get("resultUrls") or []
                if not urls:
                    raise RuntimeError("kie.ai zwróciło sukces bez URL-a grafiki")
                logger.info(f"[kie.ai] Zadanie {task_id} gotowe ({data.get('creditsConsumed')} kredytów)")
                return urls[0]

            if state == "fail":
                raise RuntimeError(f"kie.ai: generowanie nie udało się — {data.get('failMsg')}")

    raise RuntimeError(f"kie.ai: przekroczono {KIE_TIMEOUT_SECONDS}s oczekiwania")


# ──────────────────────────────────────────────────────────────────────────────
# Kampania „Twoja gmina. Na żywo.” — 27.07–10.08.2026
# ──────────────────────────────────────────────────────────────────────────────
# Copy przeniesione 1:1 z automation/n8n/kampania_C_harmonogram.json (zatwierdzone
# w COPY_HARMONOGRAM.md v2.0). Grafiki: uploads/social/kampania/ — jedyne miejsce.
#
# kind="post"     → propozycja na Telegram z przyciskiem publikacji na FB
# kind="reminder" → samo przypomnienie (materiały, które wrzucasz ręcznie: YT, Reels, Story)

CAMPAIGN_IMAGE_DIR = "kampania"

CAMPAIGN_PLAN: list[dict] = [
    {
        "at": "2026-07-26 09:00", "kind": "reminder", "title": "Story teaser (IG+FB)",
        "message": "🔔 *Story teaser — ostatni dzień!*\n\nWrzuć `story_01_teaser.png` („JUŻ 27 LIPCA”) na Instagram Story i Facebook Story.\nJutro premiera. 🚀",
    },
    {
        "at": "2026-07-26 12:00", "kind": "reminder", "title": "Załóż kanał YouTube",
        "message": "🔔 *Kanał YouTube*\n\nBanner: `DESIGN/posts/RybnoYT-Banner.png`, avatar: `RybnoYT-Avatar.png`.\nFilm gotowy: `DESIGN/video/RybnoLive_YT_16x9_20s.mp4` — publikacja jutro 8:00.\nTytuł: „Rybno Live — Twoja gmina. Na żywo. 🔵” (opis i tagi w COPY_HARMONOGRAM.md).",
    },
    {
        "at": "2026-07-27 07:45", "kind": "reminder", "title": "🚀 LAUNCH DAY",
        "message": "🚀 *LAUNCH DAY — 27 lipca*\n\n• 8:00 — publikacja filmu na YouTube\n• podmień cover FB na `cover_fb.png`\n• post „5 agentów” przyjdzie przyciskiem o 8:30\n\nPowodzenia! 🔵",
    },
    {
        "at": "2026-07-27 08:30", "kind": "post", "title": "Post launch — 5 agentów",
        "image": "post_02_agenci.png",
        "message": "Poznaj zespół, który nie śpi. 🤖\n5 asystentów AI odpowiada na pytania o Gminę Rybno — o wiadomości, urzędy, awarie, wydarzenia i terminy.\nZa darmo, na rybnolive.pl. Link w komentarzu. ⤵️\n\nrybnolive.pl — Twoja gmina. Na żywo.\n#Rybno #GminaRybno #RybnoLive #WarmiaMazury",
        "note": "➡️ Po publikacji: dodaj komentarz z linkiem https://rybnolive.pl i PRZYPNIJ post!",
    },
    {
        "at": "2026-07-27 16:45", "kind": "reminder", "title": "Reels 9:16 (IG + FB)",
        "message": "🔔 *Reels o 17:00*\n\nPlik: `DESIGN/stories/RybnoLive_Reels_9x16.mp4`\nOpis: „Cała gmina w Twojej dłoni. 🔵 rybnolive.pl”",
    },
    {
        "at": "2026-07-29 18:00", "kind": "post", "title": "Post — Redaktor (agenci)",
        "image": "karuzela_1_redaktor.png",
        "message": "Każdy z nich zna gminę od innej strony.\nRedaktor śledzi wiadomości. Urzędnik zna BIP na pamięć. Strażnik pilnuje awarii. Przewodnik wie, co w weekend. Organizator pamięta każdy termin wywozu.\nWybierz swojego → rybnolive.pl\n\n#Rybno #GminaRybno #RybnoLive #WarmiaMazury",
    },
    {
        "at": "2026-07-30 16:45", "kind": "reminder", "title": "Reels animowany + START BOOST ADS",
        "message": "🔔 *17:00 — Reels animowany*\n\n`DESIGN/video/RybnoLive_Reels_Animowany_10s.mp4` (IG + FB Reels + YT Shorts)\n\n💰 *Start płatnej promocji:* 300–500 zł / 2 tyg.\nGeotargeting: Rybno + Działdowo + Lidzbark 25 km, 25–65 lat.\nBoostuj: post „agenci” + Reels.",
    },
    {
        "at": "2026-07-31 16:45", "kind": "reminder", "title": "Short „Pogoda”",
        "message": "🔔 *Short „Pogoda”*\n\nYT Shorts + IG/FB Reels: `DESIGN/stories/RybnoShort-Pogoda.mp4`\nPost weekendowy przyjdzie przyciskiem o 17:00.",
    },
    {
        "at": "2026-07-31 17:00", "kind": "post", "title": "Post weekend — Przewodnik",
        "image": "post_03_cta_weekend.png",
        "message": "Piątek. To co robimy w weekend? 🌤️\nWydarzenia, kino w Działdowie i atrakcje okolicy — Przewodnik zna odpowiedź w 5 sekund.\nZapytaj na rybnolive.pl\n\nrybnolive.pl — Twoja gmina. Na żywo.\n#Rybno #GminaRybno #RybnoLive #Działdowo",
    },
    {
        "at": "2026-08-03 09:45", "kind": "reminder", "title": "Short „Awarie”",
        "message": "🔔 *Short „Awarie”*\n\nYT Shorts + IG/FB Reels: `DESIGN/stories/RybnoShort-Awarie.mp4`\nPost o awariach przyjdzie przyciskiem o 10:00.",
    },
    {
        "at": "2026-08-03 10:00", "kind": "post", "title": "Post awarie — Strażnik",
        "image": "post_04_awarie.png",
        "message": "Prąd wysiadł? My już o tym piszemy. ⚡\nAwarie, utrudnienia i alerty RCB — zanim zdążysz zapytać sąsiada.\nStrażnik czuwa 24/7 na rybnolive.pl\n\nrybnolive.pl — Twoja gmina. Na żywo.\n#Rybno #GminaRybno #RybnoLive #PowiatDziałdowski",
    },
    {
        "at": "2026-08-05 17:00", "kind": "post", "title": "Post — Urzędnik",
        "image": "karuzela_2_urzednik.png",
        "message": "Przetargi, uchwały, ogłoszenia z BIP-u. 📋\nUrzędnik czyta to wszystko za Ciebie i odpowiada prostym językiem.\nSprawdź na rybnolive.pl\n\nrybnolive.pl — Twoja gmina. Na żywo.\n#Rybno #GminaRybno #RybnoLive",
    },
    {
        "at": "2026-08-07 17:00", "kind": "post", "title": "Post — Organizator (odpady)",
        "image": "karuzela_5_organizator.png",
        # ⚠️ Było „wszystkich 24 sołectw” i to nieprawda w obie strony: sołectw jest
        # 20 (gmina_facts.SOLECTWA), miejscowości 22 (alert_policy.GMINA_RYBNO_PLACES),
        # a 24 to liczba POZYCJI w waste_schedule — bo Rybno ma dwa rejony wywozu
        # (R1, R2) i osobno stoją domki letniskowe. W gminie, gdzie każdy zna swoje
        # sołectwo, taka liczba kosztuje wiarygodność całego serwisu.
        "message": "Kiedy wywóz w Twojej miejscowości? 🗓️\nOrganizator zna harmonogram całej gminy Rybno — na pamięć.\nZapytaj na rybnolive.pl\n\nrybnolive.pl — Twoja gmina. Na żywo.\n#Rybno #GminaRybno #RybnoLive",
    },
    {
        "at": "2026-08-10 10:00", "kind": "reminder", "title": "📊 KPI-check kampanii",
        "message": "📊 *KPI-check kampanii*\n\nSprawdź: zasięgi postów, obserwujących FB/IG, wyświetlenia YT, rejestracje na rybnolive.pl.\n\n⚠️ *Dezaktywuj workflow „RybnoLive — kampania”* — harmonogram się skończył.",
    },
]

# Story teaser dzienne przypomnienia trwają do 26.07 — obsłużone wpisami wyżej.
# Story pogodowe 4–9.08 7:15 celowo pominięte: generator story_pogoda() nie jest gotowy,
# a codzienne puste przypomnienie tylko zaśmieca Telegram.


def find_due_campaign_item(now: Optional[datetime] = None, tolerance_minutes: int = 10) -> Optional[dict]:
    """
    Znajdź pozycję kampanii zaplanowaną na „teraz” (okno tolerancji na opóźnienie crona).

    Gdy w oknie mieści się więcej niż jedna pozycja, wygrywa NAJPÓŹNIEJSZA. Bez tego
    o 10:00 zwracane było przypomnienie z 9:45 zamiast posta z 10:00 — takie pary
    (przypomnienie o materiale ręcznym, kwadrans później post) są w planie regułą.

    Zwraca None, gdy nic nie przypada — wtedy workflow w n8n kończy się na pierwszym IF-ie.
    """
    now = now or datetime.now()
    window_start = now - timedelta(minutes=tolerance_minutes)

    candidates = [
        (datetime.strptime(item["at"], "%Y-%m-%d %H:%M"), item)
        for item in CAMPAIGN_PLAN
    ]
    due = [(scheduled, item) for scheduled, item in candidates if window_start <= scheduled <= now]
    if not due:
        return None
    return max(due, key=lambda pair: pair[0])[1]
