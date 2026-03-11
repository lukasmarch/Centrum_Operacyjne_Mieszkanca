"""
Zgłoszenie24 – AI Report Analyzer
Uses Gemini Vision API to analyze citizen report images and text.
Enhanced with Gmina Rybno-specific priority rules.
"""
import json
import logging
import base64
from typing import Optional, Dict, Any

import google.generativeai as genai
from ..config import settings

logger = logging.getLogger(__name__)


def _get_model():
    """Initialize Gemini model with API key."""
    genai.configure(api_key=settings.GEMINI_API_KEY)
    return genai.GenerativeModel("gemini-2.0-flash")


ANALYSIS_PROMPT = """Jesteś dyżurnym operatorem Centrum Powiadamiania o Zdarzeniach w gminie Rybno (powiat działdowski, woj. warmińsko-mazurskie).

KONTEKST TERENU:
- Gmina Rybno to teren wiejsko-miejski z licznymi jeziorami (Jezioro Rumian, Jezioro Rybno, okoliczne stawy)
- Dużo dróg gruntowych i mostków
- Teren leśny, zagrożenie pożarowe w sezonie letnim
- Infrastruktura wodociągowo-kanalizacyjna wymaga częstych napraw
- Miejscowości: Rybno, Hartowiec, Rumian, Żabiny, Koszelewki, Jeżewo, Dłutowo, Fijewo i inne

{image_instruction}

Opis zgłoszenia od mieszkańca:
"{description}"

{location_instruction}

Twoim zadaniem jest:
1. Określić kategorię problemu (BARDZO WAŻNE – wybierz precyzyjnie)
2. Wykryć obiekty na zdjęciu (jeśli dołączono)
3. Ocenić stan / wagę problemu i przydzielić priorytet
4. Wygenerować krótkie streszczenie zgłoszenia (1-2 zdania) – JEŚLI DOŁĄCZONO ZDJĘCIE, streszczenie MUSI zawierać krótki opis tego co widać na zdjęciu (np. "Na zdjęciu widać dużą dziurę w asfalcie...", "Zdjęcie przedstawia powalone drzewo blokujące jezdnię...")
5. Sprawdzić czy zgłoszenie nie jest spamem lub nie zawiera treści obraźliwych

Odpowiedz WYŁĄCZNIE w formacie JSON (bez markdown, bez komentarzy):
{{
  "category": "emergency|fire|infrastructure|water|safety|waste|greenery|other",
  "detected_objects": ["obiekt1", "obiekt2"],
  "condition": "opis stanu problemu i ocena zagrożenia",
  "summary": "Krótkie streszczenie po polsku (1-2 zdania). Jeśli jest zdjęcie – zacznij od opisu tego co na nim widać, potem połącz z opisem tekstowym mieszkańca.",
  "severity": "low|medium|high|critical",
  "is_spam": false,
  "spam_reason": null,
  "suggested_title": "Sugerowany krótki tytuł zgłoszenia"
}}

═══════════════════════════════════════
KATEGORIE (uporządkowane wg priorytetu):
═══════════════════════════════════════

🚨 emergency (NAJWYŻSZY PRIORYTET):
   Wypadki drogowe, tonięcie/zagrożenie w wodzie, osoby poszkodowane,
   zawalenie budynku, wypadek z udziałem osób, sytuacje zagrażające życiu.
   → severity = "critical" ZAWSZE

🔥 fire (WYSOKI PRIORYTET):
   Pożary budynków, pożary lasów/traw, zadymienie, tlące się ognisko w lesie,
   wypalanie traw, podpalenia, zagrożenie pożarowe.
   → severity = "critical" lub "high"

🏗️ infrastructure (PRIORYTET STANDARDOWY):
   Drogi: dziury, uszkodzenia nawierzchni, rozjechane pobocza, połamane barierki
   Chodniki: uszkodzone płyty, brak oświetlenia, zepsute latarnie
   Mosty/przepusty: uszkodzenia, podmycia, brak oznakowania
   Przystanki: zniszczone wiaty, brak rozkładu jazdy
   Budynki użyteczności publicznej: uszkodzenia, graffiti
   → severity = "medium" do "high"

💧 water (PRIORYTET STANDARDOWY):
   Pęknięte rury, awarie wodociągów, wycieki wody, zalania
   Awarie kanalizacji, przepełnione studzienki, smród z kanalizacji
   Zanieczyszczenie jezior lub cieków wodnych
   Podniesiony poziom wody w jeziorach (zagrożenie powodziowe → "critical")
   → severity = "medium" do "critical" (critical jeśli zagrożenie powodziowe)

⚠️ safety (PRIORYTET STANDARDOWY):
   Brakujące/uszkodzone znaki drogowe, brak oznakowania
   Niebezpieczne skrzyżowania, brak przejść dla pieszych
   Uszkodzone bariery ochronne, nieogrodzony plac budowy
   Dzikie zwierzęta na drodze, niebezpieczne drzewa nad drogą
   → severity = "medium" do "high"

🗑️ waste:
   Dzikie wysypiska śmieci, przepełnione kosze, odpady wielkogabarytowe
   Nielegalne składowiska, śmieci w lesie/przy jeziorze
   → severity = "low" do "medium"

🌳 greenery:
   Powalone drzewa (na drogę → "high"), zarośnięte chodniki
   Zniszczone tereny zielone, uszkodzone ławki/place zabaw
   → severity = "low" do "high" (jeśli drzewo blokuje drogę/zagraża)

📋 other:
   Wszystko co nie pasuje do powyższych kategorii
   → severity = "low" do "medium"

═══════════════════════════════════════
ZASADY PRIORYTETOWANIA:
═══════════════════════════════════════

severity = "critical" (ALARM):
  ✅ Zagrożenie życia lub zdrowia ludzi
  ✅ Wypadek z poszkodowanymi
  ✅ Tonięcie lub zagrożenie utonięciem
  ✅ Pożar budynku, lasu
  ✅ Zawalenie się konstrukcji
  ✅ Zagrożenie powodziowe
  ✅ Wyciek gazu lub substancji niebezpiecznych

severity = "high" (PILNE):
  ✅ Awaria infrastruktury krytycznej (wodociąg, kanalizacja, prąd)
  ✅ Pęknięta rura z dużym wyciekiem
  ✅ Drzewo spadłe na drogę/samochód
  ✅ Duża dziura w drodze zagrażająca kierowcom
  ✅ Brak oświetlenia na głównej drodze
  ✅ Pożar trawy w pobliżu zabudowań

severity = "medium" (STANDARDOWY):
  ✅ Mniejsze uszkodzenia dróg i chodników
  ✅ Zepsuta latarnia
  ✅ Przepełniony kosz na śmieci
  ✅ Uszkodzony znak drogowy
  ✅ Drobna awaria wodociągu/kanalizacji

severity = "low" (INFORMACYJNY):
  ✅ Zaśmiecony teren
  ✅ Zarośnięte chwasty
  ✅ Drobne niedogodności estetyczne
  ✅ Sugestie usprawnień

═══════════════════════════════════════
WAŻNE ZASADY:
═══════════════════════════════════════
- is_spam = true jeśli: treści obraźliwe, niezwiązane z gminą, reklamy, żarty
- Streszczenie pisz w 3. osobie, rzeczowo, po polsku
- suggested_title: krótki, konkretny, po polsku (max 60 znaków)
- NIGDY nie klasyfikuj wypadków/pożarów/tonięć jako "other"
- Jeśli opis wspomina o jeziorze i zagrożeniu → zawsze "emergency" + "critical"
- Pęknięta rura = "water" + minimum "high"
"""


async def analyze_report(
    description: str,
    image_bytes: Optional[bytes] = None,
    image_mime_type: str = "image/jpeg",
    location_info: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Analyze a citizen report using Gemini Vision API.
    
    Args:
        description: Text description from the user
        image_bytes: Optional image data
        image_mime_type: MIME type of the image
        location_info: Optional location string (address, coords)
    
    Returns:
        Dict with analysis results (category, objects, condition, summary, severity, is_spam)
    """
    model = _get_model()
    
    if image_bytes:
        image_instruction = "Zdjęcie zostało dołączone do zgłoszenia. Przeanalizuj je dokładnie – szukaj zagrożeń, uszkodzeń, obiektów. W polu 'summary' KONIECZNIE opisz krótko co widać na zdjęciu i połącz to z opisem tekstowym mieszkańca."
    else:
        image_instruction = "Brak zdjęcia – analizuj wyłącznie na podstawie opisu tekstowego. Bądź szczególnie wyczulony na słowa kluczowe wskazujące na zagrożenie."
    
    if location_info:
        location_instruction = f"Lokalizacja zdarzenia: {location_info}"
    else:
        location_instruction = "Lokalizacja: nie podano."
    
    prompt = ANALYSIS_PROMPT.format(
        description=description,
        image_instruction=image_instruction,
        location_instruction=location_instruction,
    )
    
    try:
        if image_bytes:
            # Vision analysis with image
            image_part = {
                "mime_type": image_mime_type,
                "data": base64.b64encode(image_bytes).decode("utf-8")
            }
            response = model.generate_content([prompt, image_part])
        else:
            # Text-only analysis
            response = model.generate_content(prompt)
        
        result_text = response.text.strip()
        
        # Clean up markdown formatting if present
        if result_text.startswith("```"):
            result_text = result_text.split("\n", 1)[1]  # Remove first line
            if result_text.endswith("```"):
                result_text = result_text[:-3]
            result_text = result_text.strip()
        
        result = json.loads(result_text)
        
        # Validate required fields
        valid_categories = ["emergency", "fire", "infrastructure", "waste", "greenery", "safety", "water", "other"]
        if result.get("category") not in valid_categories:
            result["category"] = "other"
        
        valid_severities = ["low", "medium", "high", "critical"]
        if result.get("severity") not in valid_severities:
            result["severity"] = "medium"
        
        # ═══════════════════════════════════════
        # KEYWORD SAFETY NET (override AI mistakes)
        # ═══════════════════════════════════════
        desc_lower = description.lower()
        
        # Emergency keywords → force emergency + critical
        emergency_keywords = [
            "wypadek", "wypadku", "wypadkiem", "wypadki",
            "tonięcie", "tonie", "tonął", "utonięcie", "utonął", "utonęła",
            "poszkodowany", "poszkodowanych", "poszkodowana", "ranny", "ranna", "rannych", "ranni",
            "zawalenie", "zawalił", "zawaliła",
            "zasłabł", "zasłabła", "nieprzytomny", "nieprzytomna",
            "karetka", "pogotowie", "reanimacja",
            "kolizja", "kolizji", "zderzenie", "potrącenie", "potrącił",
            "śmiertelny", "śmierć", "zginął", "zginęła", "zginęli",
            "wyciek gazu", "gaz", "eksplozja", "wybuch",
        ]
        
        fire_keywords = [
            "pożar", "pożaru", "pożarem",
            "pali się", "płonie", "ogień", "ogniem",
            "podpalenie", "podpalono",
            "dym", "dymi się", "dymiło", "zadymienie",
            "wypalanie", "wypalają",
            "pożar lasu", "pożar traw", "pożar budynku",
            "straż pożarna", "strażacy",
        ]
        
        # Check for emergency keywords
        if result["category"] not in ("emergency",):
            for kw in emergency_keywords:
                if kw in desc_lower:
                    logger.warning(
                        f"SAFETY NET: keyword '{kw}' found → forcing category=emergency, severity=critical "
                        f"(was: category={result['category']}, severity={result['severity']})"
                    )
                    result["category"] = "emergency"
                    result["severity"] = "critical"
                    break
        
        # Check for fire keywords (only if not already emergency)
        if result["category"] not in ("emergency", "fire"):
            for kw in fire_keywords:
                if kw in desc_lower:
                    logger.warning(
                        f"SAFETY NET: keyword '{kw}' found → forcing category=fire, severity=high "
                        f"(was: category={result['category']}, severity={result['severity']})"
                    )
                    result["category"] = "fire"
                    if result["severity"] not in ("high", "critical"):
                        result["severity"] = "high"
                    break
        
        # Force critical severity for emergency and fire categories
        if result["category"] == "emergency":
            result["severity"] = "critical"
        if result["category"] == "fire" and result["severity"] not in ("high", "critical"):
            result["severity"] = "high"
        
        result.setdefault("detected_objects", [])
        result.setdefault("condition", "")
        result.setdefault("summary", description[:200])
        result.setdefault("is_spam", False)
        result.setdefault("spam_reason", None)
        result.setdefault("suggested_title", "")
        
        logger.info(
            f"Report analyzed: category={result['category']}, "
            f"severity={result['severity']}, spam={result['is_spam']}"
        )
        return result
        
    except json.JSONDecodeError as e:
        logger.warning(f"Failed to parse Gemini response as JSON: {e}")
        return _default_result(description)
    except Exception as e:
        logger.error(f"Gemini analysis failed: {e}")
        return _default_result(description)


def _default_result(description: str) -> Dict[str, Any]:
    """Fallback result when AI analysis fails."""
    return {
        "category": "other",
        "detected_objects": [],
        "condition": "",
        "summary": description[:200],
        "severity": "medium",
        "is_spam": False,
        "spam_reason": None,
        "suggested_title": ""
    }


async def generate_summary(description: str) -> str:
    """Generate a concise summary from a report description."""
    model = _get_model()
    
    prompt = f"""Wygeneruj krótkie streszczenie (1-2 zdania) tego zgłoszenia od mieszkańca gminy Rybno.
Pisz w 3. osobie, rzeczowo, po polsku.

Zgłoszenie: "{description}"

Streszczenie:"""
    
    try:
        response = model.generate_content(prompt)
        return response.text.strip()
    except Exception as e:
        logger.error(f"Summary generation failed: {e}")
        return description[:200]
