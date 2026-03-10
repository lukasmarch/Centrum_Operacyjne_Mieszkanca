"""
PlacesService — integracja z Gemini Maps grounding API

Pobiera informacje o lokalnych miejscach (restauracje, kawiarnie, hotele,
atrakcje, obiekty sportowe, przyroda) w okolicach Rybna i powiatu działdowskiego.

Model: gemini-2.5-flash z google_maps tool (Maps grounding)
"""
import os
import re
from typing import Optional
from google import genai
from google.genai import types

from src.utils.logger import setup_logger

logger = setup_logger("PlacesService")

# Kategorie zapytań i prompty
CATEGORY_PROMPTS = {
    "restaurant": "Restauracje, pizzerie, bary, lokale gastronomiczne w okolicach Rybna i powiatu działdowskiego. Podaj nazwy, adresy i krótkie opisy.",
    "cafe": "Kawiarnie, cukiernie, lodziarnie w okolicach Rybna i powiatu działdowskiego. Podaj nazwy, adresy i krótkie opisy.",
    "hotel": "Hotele, pensjonaty, agroturystyki, noclegi w okolicach Rybna i powiatu działdowskiego. Podaj nazwy, adresy i krótkie opisy.",
    "attraction": "Atrakcje turystyczne, muzea, zabytki, miejsca historyczne w okolicach Rybna i powiatu działdowskiego. Podaj nazwy, adresy i krótkie opisy.",
    "sport": "Obiekty sportowe, boiska, siłownie, baseny, kąpieliska w okolicach Rybna i powiatu działdowskiego. Podaj nazwy, adresy i krótkie opisy.",
    "nature": "Jeziora, szlaki piesze i rowerowe, lasy, rezerwaty przyrody w okolicach Rybna i powiatu działdowskiego. Podaj nazwy i krótkie opisy.",
}

# Rybno coordinates
RYBNO_LAT = 53.3456
RYBNO_LNG = 19.9012


class PlacesService:
    def __init__(self):
        from src.config import settings
        api_key = getattr(settings, "GEMINI_API_KEY", None) or os.environ.get("GOOGLE_API_KEY")

        if not api_key:
            logger.warning("GEMINI_API_KEY not set — PlacesService disabled")
            self.client = None
        else:
            self.client = genai.Client(api_key=api_key)

    async def fetch_places_for_category(self, category: str) -> list[dict]:
        """Fetch places for a single category using Gemini Maps grounding."""
        if not self.client:
            logger.warning("PlacesService: no client, returning empty")
            return []

        prompt = CATEGORY_PROMPTS.get(category)
        if not prompt:
            logger.error(f"Unknown category: {category}")
            return []

        try:
            logger.info(f"Fetching places for category: {category}")
            response = self.client.models.generate_content(
                model="gemini-2.5-flash",
                contents=prompt,
                config=types.GenerateContentConfig(
                    tools=[types.Tool(google_maps=types.GoogleMaps())],
                    response_modalities=["TEXT"],
                )
            )

            places = self._extract_places(response, category)
            logger.info(f"  Found {len(places)} places for {category}")
            return places

        except Exception as e:
            logger.error(f"Error fetching places for {category}: {e}")
            return []

    def _extract_places(self, response, category: str) -> list[dict]:
        """Extract places from Gemini Maps grounding response."""
        places = []

        if not response.candidates:
            return places

        candidate = response.candidates[0]
        text = response.text or ""

        # Extract grounding chunks with Maps data
        grounding_chunks = []
        if candidate.grounding_metadata and candidate.grounding_metadata.grounding_chunks:
            for chunk in candidate.grounding_metadata.grounding_chunks:
                if hasattr(chunk, "maps") and chunk.maps:
                    grounding_chunks.append({
                        "place_id": getattr(chunk.maps, "place_id", None) or "",
                        "title": getattr(chunk.maps, "title", None) or "",
                        "uri": getattr(chunk.maps, "uri", None) or "",
                    })

        if grounding_chunks:
            # Use grounding metadata — most reliable
            for gc in grounding_chunks:
                if not gc["place_id"] and not gc["title"]:
                    continue
                # Try to find description for this place in text
                desc = self._find_description_for_place(gc["title"], text)
                address = self._find_address_for_place(gc["title"], text)
                places.append({
                    "place_id": gc["place_id"] or f"gen_{category}_{gc['title'][:30]}",
                    "name": gc["title"],
                    "category": category,
                    "description": desc,
                    "address": address,
                    "maps_uri": gc["uri"],
                })
        else:
            # Fallback: parse from text response
            logger.info(f"  No Maps grounding chunks for {category}, parsing text")
            places = self._parse_places_from_text(text, category)

        return places

    def _find_description_for_place(self, name: str, text: str) -> Optional[str]:
        """Try to find a description line for a place name in the response text."""
        if not name or not text:
            return None
        for line in text.split("\n"):
            if name.lower() in line.lower():
                # Clean up the line
                clean = re.sub(r"^\*+\s*", "", line).strip()
                clean = re.sub(r"\*+", "", clean).strip()
                if len(clean) > len(name) + 5:
                    return clean[:2000]
        return None

    def _find_address_for_place(self, name: str, text: str) -> Optional[str]:
        """Try to extract address near the place name in text."""
        if not name or not text:
            return None
        lines = text.split("\n")
        for i, line in enumerate(lines):
            if name.lower() in line.lower():
                # Check current and next line for address patterns
                for check_line in [line] + lines[i+1:i+3]:
                    addr_match = re.search(
                        r"(?:ul\.|ulica|adres:?)\s*([^,\n]+(?:,\s*\d{2}-\d{3}\s*\w+)?)",
                        check_line, re.IGNORECASE
                    )
                    if addr_match:
                        return addr_match.group(0).strip()[:500]
        return None

    def _parse_places_from_text(self, text: str, category: str) -> list[dict]:
        """Fallback: parse places from plain text when no grounding metadata."""
        places = []
        # Match numbered or bulleted list items
        pattern = r"(?:^|\n)\s*(?:\d+[\.\)]\s*|\*+\s*|-\s*)(.+)"
        matches = re.findall(pattern, text)
        for i, match in enumerate(matches[:15]):
            name = re.sub(r"\*+", "", match).split("–")[0].split("-")[0].strip()
            name = re.sub(r"\s*\(.*?\)\s*", "", name).strip()
            if len(name) < 3 or len(name) > 200:
                continue
            desc = match.strip()[:2000]
            places.append({
                "place_id": f"text_{category}_{i}",
                "name": name,
                "category": category,
                "description": desc if desc != name else None,
                "address": None,
                "maps_uri": None,
            })
        return places


# Singleton
places_service = PlacesService()
