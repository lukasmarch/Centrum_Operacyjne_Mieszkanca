"""
Karta dnia — grafika do posta tekstowego, składana lokalnie z fontu i kadru kuli.

Dlaczego nie kie.ai: post tekstowy idzie CODZIENNIE, a grafika z modelu kosztuje ~22
kredyty i ~47 s. Tutaj nie ma nic do wymyślenia — nagłówek już istnieje w bazie,
trzeba go tylko złożyć. Renderujemy go dosłownie, więc znika też ryzyko, które
zmaterializowało się na produkcji przy grafikach AI: model pociął wyrazy i na obrazku
wylądowało „SPADK NIKÓW MIESZKAŃCÓW”.

Podział: kie.ai (W2, wt/czw) robi ilustracje scen — tego Pillow nie zrobi.
Ten moduł (W1, codziennie) robi kartę typograficzną — tego nie warto zlecać modelowi.

Wymiary 1200×630 to format karty linku FB/OG; działa też jako zwykłe zdjęcie w poście.
"""
import logging
import re
import textwrap
import unicodedata
from datetime import date
from functools import lru_cache
from io import BytesIO
from pathlib import Path
from typing import List, Optional, Tuple

from PIL import Image, ImageDraw, ImageFilter, ImageFont

logger = logging.getLogger(__name__)

ASSETS = Path(__file__).parent.parent.parent / "assets"
FONT_PATH = ASSETS / "fonts" / "Outfit.ttf"
ORB_PATH = ASSETS / "social" / "orb.jpg"

WIDTH, HEIGHT = 1200, 630
MARGIN = 72

# Kolory z DESIGN/BRAND.md — zmiana tutaj musi iść razem z tamtym plikiem.
BG = (5, 8, 15)          # --background
BLUE = (58, 129, 246)    # --chart-2, kolor główny
GLOW = (145, 197, 255)   # --chart-1
WHITE = (250, 250, 250)  # --foreground
GREY = (140, 140, 140)

DNI = ["PONIEDZIAŁEK", "WTOREK", "ŚRODA", "CZWARTEK", "PIĄTEK", "SOBOTA", "NIEDZIELA"]
MIESIACE = ["stycznia", "lutego", "marca", "kwietnia", "maja", "czerwca",
            "lipca", "sierpnia", "września", "października", "listopada", "grudnia"]

VARIATION_SELECTORS = re.compile(r"[︀-️\U000E0100-\U000E01EF]")

# (stopień pisma, znaków w wierszu) — pierwszy układ mieszczący się w 4 wierszach wygrywa
HEADLINE_STEPS = ((66, 26), (56, 31), (48, 37), (42, 43), (36, 50))
MAX_LINES = 4


@lru_cache(maxsize=16)
def _font(size: int, weight: str = "Bold") -> ImageFont.FreeTypeFont:
    font = ImageFont.truetype(str(FONT_PATH), size)
    font.set_variation_by_name(weight)
    return font


def _strip_emoji(text: str) -> str:
    """
    Wytnij emoji — Outfit nie ma dla nich glifów i renderują się jako puste kwadraty.

    Wykryte na produkcji: nagłówek „⚠️ Wypadek na drodze…” dał na karcie dwa „tofu”
    przed tekstem. W treści posta emoji zostają — Facebook wyświetla je poprawnie,
    problem dotyczy wyłącznie tego, co wypalamy w grafice.

    Kategorie: So (symbole, w tym emoji), Cf (ZWJ i inne sterujące), Cs (surogaty).
    Selektory wariantu wycinamy zakresem, a nie kategorią: U+FE0F to `Mn`, tak samo jak
    łączone znaki diakrytyczne, których wycinać nie chcemy.
    """
    cleaned = "".join(
        ch for ch in text
        if unicodedata.category(ch) not in ("So", "Cf", "Cs") and not VARIATION_SELECTORS.match(ch)
    )
    return re.sub(r"\s+", " ", cleaned).strip(" -–—:·")


def _label_for(headline: str, day: date) -> str:
    """Etykieta w pigułce: awaria ma pierwszeństwo, poza tym data — dowód świeżości."""
    if "AWARIA" in headline.upper():
        return "AWARIA"
    return f"{DNI[day.weekday()]} · {day.day} {MIESIACE[day.month - 1].upper()}"


def _fit_headline(headline: str) -> Tuple[ImageFont.FreeTypeFont, List[str], int]:
    for size, per_line in HEADLINE_STEPS:
        lines = textwrap.wrap(headline, width=per_line)
        if len(lines) <= MAX_LINES:
            return _font(size, "ExtraBold"), lines, size
    # Nagłówek dłuższy niż jakikolwiek układ — przycinamy, wielokropek sygnalizuje ucięcie
    size, per_line = HEADLINE_STEPS[-1]
    lines = textwrap.wrap(headline, width=per_line)[:MAX_LINES]
    lines[-1] = lines[-1].rstrip(" ,.;–—") + "…"
    return _font(size, "ExtraBold"), lines, size


def render_daily_card(headline: str, day: Optional[date] = None) -> bytes:
    """Zwróć JPEG 1200×630 z nagłówkiem dnia. Bez I/O sieciowego, ~0,2 s."""
    day = day or date.today()
    headline = _strip_emoji(headline or "") or "Centrum Operacyjne Rybna"

    img = Image.new("RGB", (WIDTH, HEIGHT), BG)

    # Kula z animacji hero — wtopiona w prawą krawędź, przygaszona, żeby nie zabierała
    # uwagi nagłówkowi. Maska rozmyta, bo twarda krawędź zdradzałaby wklejony kadr.
    # Brak pliku nie może wywrócić karty: bez kuli jest skromniej, ale post wychodzi.
    try:
        orb = Image.open(ORB_PATH).convert("RGB").resize((520, 520), Image.LANCZOS)
        orb = Image.blend(Image.new("RGB", orb.size, BG), orb, 0.75)
        mask = Image.new("L", orb.size, 0)
        ImageDraw.Draw(mask).ellipse((8, 8, 512, 512), fill=255)
        img.paste(orb, (820, 210), mask.filter(ImageFilter.GaussianBlur(45)))
    except OSError as exc:
        logger.warning(f"[social_card] Pomijam kulę, nie wczytano {ORB_PATH}: {exc}")

    draw = ImageDraw.Draw(img)
    draw.rectangle((0, 0, WIDTH, 6), fill=BLUE)

    # Pigułka z etykietą
    label = _label_for(headline, day)
    label_font = _font(20, "ExtraBold")
    label_width = draw.textlength(label, font=label_font)
    draw.rounded_rectangle((MARGIN, 62, MARGIN + label_width + 44, 108), radius=23, fill=BLUE)
    draw.text((MARGIN + 22 + label_width / 2, 85), label, font=label_font, fill=WHITE, anchor="mm")

    # Nagłówek wyśrodkowany pionowo między pigułką a stopką — inaczej krótkie nagłówki
    # („Awaria wody w Rybnie”) zostawiały pod sobą pustą połowę kadru.
    head_font, lines, size = _fit_headline(headline)
    line_height = int(size * 1.22)
    block_top = 150 + (370 - len(lines) * line_height) // 2
    for index, line in enumerate(lines):
        draw.text((MARGIN, block_top + index * line_height), line,
                  font=head_font, fill=WHITE, anchor="la")

    # Stopka — cała po lewej, na czystym tle. Po prawej claim wchodził na dłoń z kadru
    # kuli i robił się nieczytelny.
    draw.line((MARGIN, 540, MARGIN + 52, 540), fill=BLUE, width=4)
    domain_font = _font(34, "SemiBold")
    draw.text((MARGIN, 562), "rybnolive.pl", font=domain_font, fill=GLOW, anchor="la")
    domain_width = draw.textlength("rybnolive.pl", font=domain_font)
    draw.text((MARGIN + domain_width + 18, 572), "· Twoja gmina. Na żywo.",
              font=_font(22, "Medium"), fill=GREY, anchor="la")

    buffer = BytesIO()
    img.save(buffer, format="JPEG", quality=90, optimize=True)
    return buffer.getvalue()
