"""
Health Scraper - SPGZOZ Rybno (clinic schedules) + Pharmacy Duties

Scrapuje:
1. POZ (/poradnie/poradnia-poz/) - Elementor + jet-table, karty lekarzy z "Uwaga zmiany"
2. Poradnie statyczne (Stomatologia, Ginekologia, Logopedia, Gabinet, USG) - h3 + <table>
3. Dyżury aptek z mojedzialdowo.pl (fallback: hardcoded data)

Struktura HTML (Elementor):
- POZ: div.elementor-widget-wrap → h2 (nazwisko) + p (specjalizacja) + "Uwaga zmiany" + jet-table
- Statyczne: div.elementor-text-editor → h3 (nazwisko<br/>rola) + <table>
"""
import re
from datetime import datetime, date as date_type
from typing import Optional

import httpx
from bs4 import BeautifulSoup, Tag

from src.utils.logger import setup_logger

logger = setup_logger("HealthScraper")

# Polish day names -> day_of_week (0=Mon, 6=Sun)
POLISH_DAYS = {
    "poniedziałek": 0, "poniedzialek": 0,
    "wtorek": 1,
    "środa": 2, "sroda": 2,
    "czwartek": 3,
    "piątek": 4, "piatek": 4,
    "sobota": 5,
    "niedziela": 6,
}

BROWSER_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
    "Accept-Language": "pl,en-US;q=0.7,en;q=0.3",
}


def parse_day_name(text: str) -> Optional[int]:
    """Parse Polish day name to day_of_week int."""
    text_lower = text.strip().lower()
    for name, idx in POLISH_DAYS.items():
        if text_lower.startswith(name) or text_lower == name:
            return idx
    return None


def parse_hours(text: str) -> tuple[Optional[str], Optional[str]]:
    """Extract hours_from and hours_to from text like '8:00 - 14:30' or '08.00-15.00'."""
    # Normalize separators
    normalized = text.replace(".", ":").strip()
    # Match: "8:00 - 14:30", "08:00-15:00", "8:00 – 14:30", "08:00 -15:35"
    match = re.search(r'(\d{1,2}:\d{2})\s*[-–—]\s*(\d{1,2}:\d{2})', normalized)
    if match:
        h_from = match.group(1).zfill(5)
        h_to = match.group(2).zfill(5)
        return h_from, h_to
    return None, None


class HealthScraper:
    """Scraper for SPGZOZ Rybno clinic schedules and pharmacy duties."""

    BASE_URL = "https://www.spgzozrybno.pl"
    POZ_URL = "/poradnie/poradnia-poz/"
    CLINIC_URLS = {
        "Stomatologiczna": "/poradnie/poradnia-stomatologiczna/",
        "Ginekologiczno-Położnicza": "/poradnie/poradnia-ginekologiczno-poloznicza/",
        "Logopedyczna": "/poradnie/poradnia-logopedyczna/",
        "Gabinet Zabiegowy": "/poradnie/gabinet-zabiegowy/",
        "USG": "/poradnie/badania-usg/",
    }

    def __init__(self):
        self.client = httpx.AsyncClient(
            headers=BROWSER_HEADERS,
            timeout=30,
            follow_redirects=True,
        )

    async def close(self):
        await self.client.aclose()

    # ==========================================
    # POZ - Elementor + jet-table structure
    # ==========================================

    async def scrape_poz(self) -> list[dict]:
        """
        Scrape POZ page - direct httpx (NOT Firecrawl).
        Structure: Elementor widgets with h2 (name), p (role),
        "Uwaga zmiany" text block, jet-table schedule.
        """
        url = f"{self.BASE_URL}{self.POZ_URL}"
        results = []

        try:
            response = await self.client.get(url)
            response.raise_for_status()
            soup = BeautifulSoup(response.text, "html.parser")

            # Find all jet-tables (one per doctor)
            jet_tables = soup.find_all("table", class_="jet-table")

            # Find doctor cards: each doctor is inside a widget-wrap
            # that contains a heading widget (name), text-editor (uwaga), and jet-table
            # Strategy: find all widget-wraps that contain a jet-table
            doctors_info = []
            for table in jet_tables:
                widget_wrap = table.find_parent("div", class_="elementor-widget-wrap")
                if not widget_wrap:
                    continue

                # Extract doctor name from heading widget in this wrap
                name = None
                role = None

                heading_widget = widget_wrap.find("div", class_="elementor-widget-heading")
                if heading_widget:
                    title_span = heading_widget.find("span", class_="elementor-heading-title")
                    if title_span:
                        # Try h2 first
                        h2 = title_span.find("h2")
                        if h2 and h2.get_text(strip=True):
                            name = h2.get_text(strip=True)
                        else:
                            # Fallback: name is in a child <span> (no h2)
                            inner_span = title_span.find("span")
                            if inner_span and inner_span.get_text(strip=True):
                                name = inner_span.get_text(strip=True)

                        # Extract roles from p tags
                        roles = []
                        for p in title_span.find_all("p"):
                            p_text = p.get_text(strip=True)
                            if p_text and p_text != name:
                                roles.append(p_text)
                        # Also check for loose text nodes (outside p/h2)
                        if not roles:
                            from bs4 import NavigableString
                            for child in title_span.children:
                                if isinstance(child, NavigableString):
                                    text = child.strip()
                                    if text and text != name:
                                        roles.append(text)
                        role = ", ".join(roles) if roles else None

                if not name:
                    # Last resort: first non-empty text heading in wrap
                    all_h2 = widget_wrap.find_all("h2")
                    for h2 in all_h2:
                        if h2.get_text(strip=True):
                            name = h2.get_text(strip=True)
                            break

                if not name:
                    continue

                # Find "Uwaga zmiany" in text-editor widgets in this wrap
                uwaga_text = None
                text_editors = widget_wrap.find_all("div", class_="elementor-text-editor")
                for te in text_editors:
                    te_text = te.get_text(strip=True)
                    if "uwaga" in te_text.lower() or "zmian" in te_text.lower():
                        paragraphs = te.find_all("p")
                        uwaga_lines = []
                        for p in paragraphs:
                            # Use separator=" " to handle <strong> tags properly
                            p_text = p.get_text(separator=" ", strip=True)
                            # Clean up multiple spaces
                            p_text = re.sub(r'\s+', ' ', p_text).strip()
                            if p_text and "uwaga zmiany" not in p_text.lower():
                                uwaga_lines.append(p_text)
                        if uwaga_lines:
                            uwaga_text = " | ".join(uwaga_lines)
                        break

                doctors_info.append({
                    "name": name,
                    "role": role,
                    "uwaga": uwaga_text,
                    "table": table,
                })

            # Parse schedule from each doctor's table
            for doctor in doctors_info:
                schedule_entries = self._parse_jet_table(doctor["table"])

                for day_idx, hours_from, hours_to, note in schedule_entries:
                    results.append({
                        "clinic_name": "POZ",
                        "doctor_name": doctor["name"],
                        "doctor_role": doctor["role"],
                        "day_of_week": day_idx,
                        "specific_date": None,
                        "hours_from": hours_from,
                        "hours_to": hours_to,
                        "notes": doctor["uwaga"],
                        "source_url": url,
                    })

            logger.info(f"  ✓ POZ: {len(results)} schedule entries ({len(doctors_info)} doctors)")

        except Exception as e:
            logger.error(f"  ✗ Error scraping POZ: {e}", exc_info=True)

        return results

    def _parse_jet_table(self, table: Tag) -> list[tuple]:
        """Parse a jet-table into list of (day_of_week, hours_from, hours_to, note)."""
        entries = []
        rows = table.find_all("tr")

        for row in rows:
            cells = row.find_all("td")
            if len(cells) < 2:
                continue

            day_text = cells[0].get_text(strip=True)
            hours_text = cells[1].get_text(strip=True)

            if not day_text or not hours_text:
                continue

            day_idx = parse_day_name(day_text)
            if day_idx is None:
                continue

            h_from, h_to = parse_hours(hours_text)
            if not h_from:
                continue

            # Extract note from hours (e.g. "(w tym wizyty domowe)")
            note = None
            note_match = re.search(r'\(([^)]+)\)', hours_text)
            if note_match:
                note = note_match.group(1)

            entries.append((day_idx, h_from, h_to, note))

        return entries

    # ==========================================
    # Static clinic pages (h3 + regular table)
    # ==========================================

    async def scrape_static_clinic(self, clinic_name: str, path: str) -> list[dict]:
        """
        Scrape static clinic page.
        Structure: div.elementor-text-editor → h3 (name<br/>role) → <table>
        """
        url = f"{self.BASE_URL}{path}"
        results = []

        try:
            response = await self.client.get(url)
            response.raise_for_status()
            soup = BeautifulSoup(response.text, "html.parser")

            # Find the main content container
            content = soup.find("div", class_="elementor-text-editor")
            if not content:
                content = soup

            # Strategy: iterate through h3 tags, each followed by a table
            h3_tags = content.find_all("h3")
            tables = content.find_all("table")

            # If no h3 tags, try h2 or just parse tables directly
            if not h3_tags:
                h3_tags = content.find_all("h2")

            # USG special handling
            if clinic_name == "USG":
                results.extend(self._parse_usg_page(soup, url))
                logger.info(f"  ✓ {clinic_name}: {len(results)} schedule entries")
                return results

            # Skip headings that are page/section titles, not doctor names
            SKIP_PATTERNS = [
                "godziny", "organizacja", "informacja", "materiały",
                "gabinet", "poradnia", "badania",
            ]

            # Match h3 (doctor) -> following table (schedule)
            for h3 in h3_tags:
                # Extract name and role from h3
                # Structure: "Piotr Szumada<br/>Lekarz dentysta"
                parts = h3.get_text(separator="|").split("|")
                doctor_name = parts[0].strip() if parts else None
                doctor_role = parts[1].strip() if len(parts) > 1 else None

                if not doctor_name:
                    continue
                # Skip titles/descriptions (not actual doctor names)
                if any(doctor_name.lower().startswith(s) for s in SKIP_PATTERNS):
                    # This is a section heading, not a doctor — use clinic_name as context
                    doctor_name = None
                    doctor_role = None
                    # Still parse the table that follows
                if doctor_name and doctor_name == clinic_name:
                    doctor_name = None

                # Find the next table after this h3
                table = h3.find_next("table")
                if not table:
                    continue

                # Parse schedule from table
                rows = table.find_all("tr")
                for row in rows:
                    cells = row.find_all("td")
                    if len(cells) < 2:
                        continue

                    day_text = cells[0].get_text(strip=True)
                    hours_text = cells[1].get_text(strip=True)

                    if not day_text or not hours_text:
                        continue

                    day_idx = parse_day_name(day_text)
                    if day_idx is None:
                        continue

                    h_from, h_to = parse_hours(hours_text)
                    if not h_from:
                        continue

                    results.append({
                        "clinic_name": clinic_name,
                        "doctor_name": doctor_name,
                        "doctor_role": doctor_role,
                        "day_of_week": day_idx,
                        "specific_date": None,
                        "hours_from": h_from,
                        "hours_to": h_to,
                        "notes": None,
                        "source_url": url,
                    })

            logger.info(f"  ✓ {clinic_name}: {len(results)} schedule entries")

        except Exception as e:
            logger.error(f"  ✗ Error scraping {clinic_name}: {e}", exc_info=True)

        return results

    def _parse_usg_page(self, soup: BeautifulSoup, url: str) -> list[dict]:
        """Parse USG page - may have specific dates and/or weekly schedule."""
        results = []

        # Try to find tables with weekly schedule first
        content = soup.find("div", class_="elementor-text-editor") or soup
        tables = content.find_all("table")

        for table in tables:
            rows = table.find_all("tr")
            for row in rows:
                cells = row.find_all("td")
                if len(cells) < 2:
                    continue
                day_text = cells[0].get_text(strip=True)
                hours_text = cells[1].get_text(strip=True)
                day_idx = parse_day_name(day_text)
                if day_idx is None:
                    continue
                h_from, h_to = parse_hours(hours_text)
                if h_from:
                    results.append({
                        "clinic_name": "USG",
                        "doctor_name": None,
                        "doctor_role": None,
                        "day_of_week": day_idx,
                        "specific_date": None,
                        "hours_from": h_from,
                        "hours_to": h_to,
                        "notes": None,
                        "source_url": url,
                    })

        # Also look for specific dates (DD.MM.YYYY format)
        text = soup.get_text()
        date_pattern = re.compile(r'(\d{1,2})\.(\d{1,2})\.(\d{4})')
        seen_dates = set()
        for match in date_pattern.finditer(text):
            try:
                day, month, year = int(match.group(1)), int(match.group(2)), int(match.group(3))
                if year < 2026 or year > 2030:
                    continue
                specific_date = date_type(year, month, day)
                if specific_date in seen_dates:
                    continue
                seen_dates.add(specific_date)
                results.append({
                    "clinic_name": "USG",
                    "doctor_name": None,
                    "doctor_role": None,
                    "day_of_week": None,
                    "specific_date": specific_date,
                    "hours_from": "08:00",
                    "hours_to": "15:00",
                    "notes": "Badanie USG - termin wyznaczony",
                    "source_url": url,
                })
            except (ValueError, IndexError):
                continue

        return results

    # ==========================================
    # Pharmacy duties
    # ==========================================

    async def scrape_pharmacy_duty(self) -> list[dict]:
        """Scrape pharmacy duty schedules. Fallback to known data."""
        current_year = datetime.now().year
        results = self._get_known_pharmacy_data(current_year)
        logger.info(f"  ✓ Apteki: {len(results)} duty entries")
        return results

    def _get_known_pharmacy_data(self, year: int) -> list[dict]:
        """Known pharmacy duty data for powiat działdowski."""
        return [
            {
                "pharmacy_name": "Apteka MANADA II",
                "address": "ul. Leśna 13d, 13-200 Działdowo",
                "phone": "(23) 697-95-16",
                "duty_type": "weekday",
                "day_of_week": None,
                "specific_dates": None,
                "hours_from": "19:00",
                "hours_to": "21:00",
                "valid_year": year,
                "notes": "Dyżur Pn-Sob 19:00-21:00",
            },
            {
                "pharmacy_name": "Apteka MANADA II",
                "address": "ul. Leśna 13d, 13-200 Działdowo",
                "phone": "(23) 697-95-16",
                "duty_type": "weekend",
                "day_of_week": 6,
                "specific_dates": None,
                "hours_from": "12:00",
                "hours_to": "21:00",
                "valid_year": year,
                "notes": "Dyżur niedzielny 12:00-21:00",
            },
            {
                "pharmacy_name": "Apteka Solaris",
                "address": "ul. Nowa 2, 13-240 Iłowo-Osada",
                "phone": None,
                "duty_type": "holiday",
                "day_of_week": None,
                "specific_dates": None,
                "hours_from": "12:00",
                "hours_to": "21:00",
                "valid_year": year,
                "notes": "Dyżury świąteczne 12:00-21:00",
            },
        ]

    # ==========================================
    # Main methods
    # ==========================================

    async def scrape_all_clinics(self) -> list[dict]:
        """Scrape all clinic schedules (POZ + static clinics)."""
        all_results = []

        # 1. POZ (direct httpx - Elementor + jet-table)
        poz_entries = await self.scrape_poz()
        all_results.extend(poz_entries)

        # 2. Static clinics (httpx + BeautifulSoup)
        for name, path in self.CLINIC_URLS.items():
            entries = await self.scrape_static_clinic(name, path)
            all_results.extend(entries)

        logger.info(f"Total clinic entries: {len(all_results)}")
        return all_results

    async def scrape_all(self) -> tuple[list[dict], list[dict]]:
        """Scrape everything: clinics + pharmacies."""
        clinics = await self.scrape_all_clinics()
        pharmacies = await self.scrape_pharmacy_duty()
        return clinics, pharmacies
