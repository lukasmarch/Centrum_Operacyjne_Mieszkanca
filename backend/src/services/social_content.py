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
BRAND_STYLE = (
    "Flat cartoon illustration for a Polish local-news brand: rounded shapes, "
    "bold clean outlines, simple cel shading, warm and human, no photorealism, no 3D render. "
    "Rural Masurian setting (fields, lake, small village houses, church tower). "
    "Strict brand palette: deep navy background (#05080f), electric blue (#3a81f6) "
    "and light blue glow (#91c5ff) as dominant accents, warm amber only as a small "
    "light source inside the scene. Cinematic rim light, subtle grain. "
    "Keep the lower third of the frame calm and uncluttered — a headline goes there. "
    "ABSOLUTELY NO text, letters, numbers, signage, captions, logos or watermarks. "
    "No glowing orb, no globe, no giant hand."
)

CLAIM_SYSTEM_PROMPT = """Jesteś dyrektorem kreatywnym lokalnego serwisu informacyjnego RybnoLive (gmina Rybno, powiat działdowski).
Na podstawie podsumowania dnia przygotuj materiał do grafiki na Facebooka.

Zwróć WYŁĄCZNIE JSON:
{
  "claim": "hasło na grafikę: 2-4 PEŁNE wyrazy, DRUKOWANYMI literami, bez kropki na końcu",
  "scene": "scena po ANGIELSKU dla modelu graficznego: KTO i CO robi, 1-2 zdania, bez tekstu na obrazku",
  "caption": "treść posta na Facebooka po polsku: 2-3 zdania, konkretnie o tym co się stało, bez hashtagów i bez linku"
}

ZASADY DLA claim — to nagłówek nakładany na grafikę:
- musi być poprawną polską frazą, zrozumiałą bez kontekstu
- NIGDY nie skracaj ani nie obcinaj wyrazów; każde słowo w pełnej formie
- lepiej użyć 2 słów niż 4 pocięte
- DOBRZE: "AWARIA WODY", "MNIEJ MIESZKAŃCÓW", "WEEKEND W GMINIE", "DNI RYBNA 2026"
- ŹLE: "SPADK NIKÓW MIESZKAŃCÓW" (pocięte wyrazy), "FACT-CHECKING GMINA RYBNO" (żargon),
  "SPADEK LICZBY MIESZKAŃCÓW GMINY RYBNO W ROKU 2026" (za długie)

ZASADY DLA scene — grafika ma POKAZAĆ SYTUACJĘ, nie jej symbol:
- ZAWSZE są na niej ludzie i ZAWSZE coś robią; scena bez postaci jest błędem
- czynność musi wynikać wprost ze zdarzenia i oddawać jego realia:
  • awaria, utrudnienie, ostrzeżenie → widać SKUTEK dla mieszkańców
    (wyłączony prąd: rodzina w ciemnej kuchni przy świecach i latarce w telefonie;
     awaria wody: sąsiedzi z kanistrami przy beczkowozie;
     objazd: kierowcy zawracający przed zamkniętą drogą)
  • wydarzenie, sukces, dobra wiadomość → mieszkańcy biorą w nim CZYNNY udział
    (festyn: ludzie tańczą przy scenie, dzieci z watą cukrową;
     inwestycja: robotnicy i mieszkańcy oglądający nowy chodnik)
- konkret zamiast metafory: NIE "a symbol of a power outage", tylko
  "a family sitting around a candle in a dark kitchen, one child holding a phone torch"
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
    scene = (data.get("scene") or "A quiet Masurian village at golden hour").strip()
    caption = (data.get("caption") or highlights[:300]).strip()

    # Model dostaje wyłącznie scenę i styl — żadnego tekstu do narysowania. Claim
    # nakładamy potem sami (social_card.compose_photo_card), więc polskie znaki
    # i krój są pewne, a nie zależne od tego, co model zrozumie z liter.
    prompt = f"Vertical 9:16 composition. {scene} {BRAND_STYLE}"

    # Claim NIE wchodzi do treści posta — jest już wypalony na grafice, a powtórzenie
    # wyglądałoby jak błąd. (Nie używamy tu capitalize(): psuje nazwy własne — „w rybnie”.)
    message = f"{caption}\n\n👉 {SITE_URL}\n{HASHTAGS}"

    return {
        "kind": "photo",
        "message": message,
        "claim": claim,
        "prompt": prompt,
        "date": content.get("date") or summary.get("date"),
    }


# ──────────────────────────────────────────────────────────────────────────────
# kie.ai — generowanie grafiki
# ──────────────────────────────────────────────────────────────────────────────

KIE_BASE = "https://api.kie.ai/api/v1/jobs"
KIE_POLL_INTERVAL = 5.0
KIE_TIMEOUT_SECONDS = 180


async def generate_image(prompt: str, aspect_ratio: str = "9:16", resolution: str = "2K") -> str:
    """
    Wygeneruj grafikę w kie.ai i zwróć jej (tymczasowy!) URL.

    Zwracany link żyje ~24h — dlatego wywołujący MUSI go od razu zapisać u nas
    (patrz store_image_from_url w endpoints/social.py).
    """
    if not settings.KIE_API_KEY:
        raise RuntimeError("Brak KIE_API_KEY — generowanie grafik wyłączone")

    headers = {"Authorization": f"Bearer {settings.KIE_API_KEY}"}
    payload = {
        "model": settings.KIE_MODEL,
        "input": {
            "prompt": prompt,
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
        "message": "Kiedy wywóz w Twojej miejscowości? 🗓️\nOrganizator zna harmonogram dla wszystkich 24 sołectw gminy Rybno — na pamięć.\nZapytaj na rybnolive.pl\n\nrybnolive.pl — Twoja gmina. Na żywo.\n#Rybno #GminaRybno #RybnoLive",
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
