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

# Kula: rozmiar i lewy górny róg. Dobrane tak, by cały kadr (kula, poświata, dłoń)
# zmieścił się z marginesem — prawa krawędź 1160/1200, dolna 545/630.
ORB_SIZE = 460
ORB_POS = (700, 85)

VARIATION_SELECTORS = re.compile(r"[︀-️\U000E0100-\U000E01EF]")

# Kolumna tekstu kończy się przed kulą — stąd zawijanie po realnej szerokości w pikselach,
# a nie po liczbie znaków: „Truszczyny-Dębień” zajmuje dwa razy tyle co „Wery w Rybnie”
# przy tej samej długości w znakach, więc limit znakowy albo marnował miejsce, albo wpuszczał
# tekst w poświatę.
TEXT_MAX_WIDTH = ORB_POS[0] - MARGIN - 30
HEADLINE_SIZES = (66, 58, 50, 44, 38)
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


# Miejsca, w których wolno złamać JEDEN wyraz, gdy sam nie mieści się w kolumnie.
# „TUCZKI–KOSZELEWY" to dla `str.split()` jeden token, więc bez tego wyjeżdżał za kadr
# przy każdym rozmiarze fontu — a nazwa z półpauzą to w tej gminie norma, nie wyjątek.
_BREAKABLE = re.compile(r"(?<=[–\-/])")


def _split_long_word(word: str, font: ImageFont.FreeTypeFont, max_width: int) -> List[str]:
    """Rozbij wyraz na kawałki po półpauzie/łączniku. Znak łamania zostaje na końcu wiersza."""
    if font.getlength(word) <= max_width:
        return [word]
    parts = [p for p in _BREAKABLE.split(word) if p]
    if len(parts) < 2:
        return [word]                        # nie ma gdzie złamać — zostaje na zwężenie fontu
    chunks: List[str] = []
    current = ""
    for part in parts:
        candidate = current + part
        if not current or font.getlength(candidate) <= max_width:
            current = candidate
        else:
            chunks.append(current)
            current = part
    if current:
        chunks.append(current)
    return chunks


def _wrap_to_width(text: str, font: ImageFont.FreeTypeFont, max_width: int) -> List[str]:
    """Zawiń tekst tak, by żaden wiersz nie przekroczył max_width w pikselach."""
    lines: List[str] = []
    current = ""
    for word in text.split():
        for piece in _split_long_word(word, font, max_width):
            candidate = f"{current} {piece}".strip()
            if not current or font.getlength(candidate) <= max_width:
                current = candidate
            else:
                lines.append(current)
                current = piece
            if piece is not word and current and font.getlength(current) >= max_width * 0.98:
                lines.append(current)        # kawałek z łącznikiem domyka wiersz
                current = ""
    if current:
        lines.append(current)
    return lines


def _fit_headline(
    headline: str,
    max_width: int = TEXT_MAX_WIDTH,
    sizes: Tuple[int, ...] = HEADLINE_SIZES,
    max_lines: int = MAX_LINES,
) -> Tuple[ImageFont.FreeTypeFont, List[str], int]:
    for size in sizes:
        font = _font(size, "ExtraBold")
        lines = _wrap_to_width(headline, font, max_width)
        if len(lines) <= max_lines and all(font.getlength(l) <= max_width for l in lines):
            return font, lines, size
    # Nagłówek dłuższy niż jakikolwiek układ — przycinamy, wielokropek sygnalizuje ucięcie
    size = sizes[-1]
    font = _font(size, "ExtraBold")
    lines = _wrap_to_width(headline, font, max_width)[:max_lines]
    lines[-1] = lines[-1].rstrip(" ,.;–—") + "…"
    return font, lines, size


def render_daily_card(headline: str, day: Optional[date] = None) -> bytes:
    """Zwróć JPEG 1200×630 z nagłówkiem dnia. Bez I/O sieciowego, ~0,2 s."""
    day = day or date.today()
    headline = _strip_emoji(headline or "") or "Centrum Operacyjne Rybna"

    img = Image.new("RGB", (WIDTH, HEIGHT), BG)

    # Kula z animacji hero — przygaszona, żeby nie zabierała uwagi nagłówkowi.
    # Mieści się w kadrze W CAŁOŚCI, razem z dłonią: pierwsza wersja wychodziła poza
    # prawą i dolną krawędź, więc dłoń była ucięta w połowie.
    # Maska rozmyta, bo twarda krawędź zdradzałaby wklejony kadr.
    # Brak pliku nie może wywrócić karty: bez kuli jest skromniej, ale post wychodzi.
    try:
        orb = Image.open(ORB_PATH).convert("RGB").resize((ORB_SIZE, ORB_SIZE), Image.LANCZOS)
        orb = Image.blend(Image.new("RGB", orb.size, BG), orb, 0.75)
        mask = Image.new("L", orb.size, 0)
        ImageDraw.Draw(mask).ellipse((6, 6, ORB_SIZE - 6, ORB_SIZE - 6), fill=255)
        img.paste(orb, ORB_POS, mask.filter(ImageFilter.GaussianBlur(40)))
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


# ──────────────────────────────────────────────────────────────────────────────
# Post graficzny (W2) — ilustracja z kie.ai + nasza typografia
# ──────────────────────────────────────────────────────────────────────────────

PHOTO_WIDTH, PHOTO_HEIGHT = 1080, 1920
PHOTO_MARGIN = 84
PHOTO_TEXT_WIDTH = PHOTO_WIDTH - 2 * PHOTO_MARGIN
PHOTO_CLAIM_SIZES = (128, 112, 96, 84, 72)
PHOTO_MAX_LINES = 3

# Gradient zaczyna się w połowie kadru — niżej napis wchodziłby w ilustrację, wyżej
# gradient zjadałby scenę, którą model dostał w zadaniu do pokazania.
GRADIENT_TOP = int(PHOTO_HEIGHT * 0.50)


def _cover(image: Image.Image, width: int, height: int) -> Image.Image:
    """Przeskaluj z zachowaniem proporcji i przytnij do kadru (jak CSS object-fit: cover)."""
    scale = max(width / image.width, height / image.height)
    resized = image.resize((max(1, round(image.width * scale)), max(1, round(image.height * scale))), Image.LANCZOS)
    left = (resized.width - width) // 2
    top = (resized.height - height) // 2
    return resized.crop((left, top, left + width, top + height))


def _draw_photo_layers(
    base: Image.Image, claim: str, day: date, label: Optional[str] = None
) -> Image.Image:
    """
    Nałóż na `base` (RGBA 1080×1920) gradient, pigułkę, nagłówek i stopkę marki.

    `base` z pełną alfą to post graficzny; `base` przezroczysty to nakładka na wideo.
    Jedna funkcja dla obu, bo inaczej napis w rolce prędzej czy później rozjedzie się
    z napisem w poście — a to ta sama seria i widz to widzi z miniatury.
    """
    overlay = Image.new("RGBA", (PHOTO_WIDTH, PHOTO_HEIGHT), BG + (0,))
    draw_overlay = ImageDraw.Draw(overlay)
    for y in range(GRADIENT_TOP, PHOTO_HEIGHT):
        progress = (y - GRADIENT_TOP) / (PHOTO_HEIGHT - GRADIENT_TOP)
        draw_overlay.line([(0, y), (PHOTO_WIDTH, y)], fill=BG + (int(245 * progress ** 1.6),))
    img = Image.alpha_composite(base, overlay)

    draw = ImageDraw.Draw(img)
    draw.rectangle((0, 0, PHOTO_WIDTH, 8), fill=BLUE)

    # Pigułka: ta sama logika co na karcie dnia (awaria ma pierwszeństwo nad datą),
    # żeby oba rodzaje postów czytało się jak jedną serię. `label` nadpisuje ją, gdy
    # materiał nie jest o dniu, a o etapie sprawy („ZAKOŃCZENIE PRAC").
    pill = (label or _label_for(claim, day)).upper()
    label_font = _font(30, "ExtraBold")
    label_width = draw.textlength(pill, font=label_font)
    draw.rounded_rectangle((PHOTO_MARGIN, 88, PHOTO_MARGIN + label_width + 64, 156), radius=34, fill=BLUE)
    draw.text((PHOTO_MARGIN + 32 + label_width / 2, 122), pill, font=label_font, fill=WHITE, anchor="mm")

    # Blok tekstu kotwiczony do DOŁU kadru: nagłówek rośnie w górę, więc stopka zostaje
    # w tym samym miejscu niezależnie od tego, czy claim ma jedną linię czy trzy.
    claim_font, lines, size = _fit_headline(claim, PHOTO_TEXT_WIDTH, PHOTO_CLAIM_SIZES, PHOTO_MAX_LINES)
    line_height = int(size * 1.14)
    footer_top = PHOTO_HEIGHT - 232
    block_bottom = footer_top - 56
    for index, line in enumerate(reversed(lines)):
        draw.text((PHOTO_MARGIN, block_bottom - index * line_height), line,
                  font=claim_font, fill=WHITE, anchor="ls")

    draw.line((PHOTO_MARGIN, footer_top, PHOTO_MARGIN + 72, footer_top), fill=BLUE, width=6)
    domain_font = _font(50, "SemiBold")
    draw.text((PHOTO_MARGIN, footer_top + 34), "rybnolive.pl", font=domain_font, fill=GLOW, anchor="la")
    draw.text((PHOTO_MARGIN, footer_top + 106), "Twoja gmina. Na żywo.",
              font=_font(34, "Medium"), fill=GREY, anchor="la")
    return img


def compose_photo_card(illustration: bytes, claim: str, day: Optional[date] = None,
                       label: Optional[str] = None) -> bytes:
    """
    Zwróć JPEG 1080×1920: ilustracja z kie.ai pod spodem, nasza typografia na wierzchu.

    Model rysuje wyłącznie scenę — ani jednej litery (patrz BRAND_STYLE). Nagłówek,
    pigułkę i stopkę składamy tutaj, fontem Outfit i kolorami z DESIGN/BRAND.md.
    Dzięki temu każdy post ma ten sam krój, te same kolory i poprawne ogonki,
    niezależnie od tego, co model zrobiłby z polskim tekstem.
    """
    day = day or date.today()
    claim = _strip_emoji(claim or "").upper() or "RYBNO NA ŻYWO"

    base = _cover(Image.open(BytesIO(illustration)).convert("RGB"), PHOTO_WIDTH, PHOTO_HEIGHT)
    img = _draw_photo_layers(base.convert("RGBA"), claim, day, label).convert("RGB")

    buffer = BytesIO()
    img.save(buffer, format="JPEG", quality=92, optimize=True)
    return buffer.getvalue()


def render_photo_overlay(claim: str, day: Optional[date] = None,
                         label: Optional[str] = None) -> bytes:
    """
    Zwróć PNG 1080×1920 z alfą: sama warstwa marki, bez obrazu pod spodem.

    Do nakładania ffmpegiem na WŁASNY materiał wideo. Napis wychodzi identyczny jak
    na poście graficznym — ten sam font, te same współrzędne, ten sam gradient —
    bo obie ścieżki przechodzą przez `_draw_photo_layers`.
    """
    day = day or date.today()
    claim = _strip_emoji(claim or "").upper() or "RYBNO NA ŻYWO"

    base = Image.new("RGBA", (PHOTO_WIDTH, PHOTO_HEIGHT), (0, 0, 0, 0))
    buffer = BytesIO()
    _draw_photo_layers(base, claim, day, label).save(buffer, format="PNG")
    return buffer.getvalue()
