"""
Health Scraper - SPGZOZ Rybno (clinic schedules) + Pharmacy Duties

Scrapuje:
1. Poradnie SPGZOZ Rybno (5 statycznych + POZ via Firecrawl)
2. Dyzury aptek z mojedzialdowo.pl
"""
import re
from datetime import datetime, date as date_type
from typing import Optional

import httpx
from bs4 import BeautifulSoup

from src.integrations.firecrawl_client import firecrawl_client
from src.utils.logger import setup_logger

logger = setup_logger("HealthScraper")

# Polish day names -> day_of_week (0=Mon, 6=Sun)
POLISH_DAYS = {
    "poniedziałek": 0, "poniedzialek": 0, "pon": 0,
    "wtorek": 1, "wt": 1,
    "środa": 2, "sroda": 2, "śr": 2, "sr": 2,
    "czwartek": 3, "czw": 3,
    "piątek": 4, "piatek": 4, "pt": 4,
    "sobota": 5, "sob": 5,
    "niedziela": 6, "nd": 6, "niedz": 6,
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
        if name in text_lower:
            return idx
    return None


def parse_hours(text: str) -> tuple[Optional[str], Optional[str]]:
    """Extract hours_from and hours_to from text like '8:00 - 14:30' or '08.00-15.00'."""
    text = text.replace(".", ":").replace(",", ":").strip()
    # Match patterns like "8:00 - 14:30", "08:00-15:00", "8:00 do 14:30"
    match = re.search(r'(\d{1,2}:\d{2})\s*[-–—do]+\s*(\d{1,2}:\d{2})', text)
    if match:
        h_from = match.group(1).zfill(5)  # "8:00" -> "08:00"
        h_to = match.group(2).zfill(5)
        return h_from, h_to
    return None, None


class HealthScraper:
    """Scraper for SPGZOZ Rybno clinic schedules and pharmacy duties."""

    BASE_URL = "https://www.spgzozrybno.pl"
    CLINIC_URLS = {
        "Stomatologiczna": "/poradnie/poradnia-stomatologiczna/",
        "Ginekologiczno-Położnicza": "/poradnie/poradnia-ginekologiczno-poloznicza/",
        "Logopedyczna": "/poradnie/poradnia-logopedyczna/",
        "Gabinet Zabiegowy": "/poradnie/gabinet-zabiegowy/",
        "USG": "/poradnie/badania-usg/",
    }
    PHARMACY_URL = "https://mojedzialdowo.pl/dyzury-aptek/"

    def __init__(self):
        self.client = httpx.AsyncClient(
            headers=BROWSER_HEADERS,
            timeout=30,
            follow_redirects=True,
        )

    async def close(self):
        await self.client.aclose()

    # ==========================================
    # Static clinic pages (HTML table parsing)
    # ==========================================

    async def scrape_static_clinic(self, name: str, path: str) -> list[dict]:
        """Scrape a static clinic page (h3/h4 + table)."""
        url = f"{self.BASE_URL}{path}"
        results = []

        try:
            response = await self.client.get(url)
            response.raise_for_status()
            soup = BeautifulSoup(response.text, "html.parser")

            # Find tables with schedule data
            tables = soup.find_all("table")
            for table in tables:
                rows = table.find_all("tr")
                for row in rows:
                    cells = row.find_all(["td", "th"])
                    if len(cells) < 2:
                        continue

                    cell_texts = [c.get_text(strip=True) for c in cells]

                    # Try to extract day and hours from cells
                    day_idx = None
                    hours_from = None
                    hours_to = None
                    doctor = None
                    role = None

                    for i, text in enumerate(cell_texts):
                        d = parse_day_name(text)
                        if d is not None:
                            day_idx = d
                        h_from, h_to = parse_hours(text)
                        if h_from:
                            hours_from = h_from
                            hours_to = h_to

                    # Check for doctor name (cells that aren't days/hours)
                    for text in cell_texts:
                        if parse_day_name(text) is None and not re.search(r'\d{1,2}:\d{2}', text.replace(".", ":")):
                            if len(text) > 3 and text not in ("Dzień", "Godziny", "Lekarz", ""):
                                if not doctor:
                                    doctor = text
                                elif not role:
                                    role = text

                    if day_idx is not None and hours_from:
                        results.append({
                            "clinic_name": name,
                            "doctor_name": doctor,
                            "doctor_role": role,
                            "day_of_week": day_idx,
                            "specific_date": None,
                            "hours_from": hours_from,
                            "hours_to": hours_to,
                            "notes": None,
                            "source_url": url,
                        })

            # USG special: look for specific dates
            if name == "USG":
                results.extend(self._parse_usg_dates(soup, url))

            logger.info(f"  ✓ {name}: {len(results)} schedule entries")

        except Exception as e:
            logger.error(f"  ✗ Error scraping {name}: {e}")

        return results

    def _parse_usg_dates(self, soup: BeautifulSoup, url: str) -> list[dict]:
        """Parse USG specific dates from page content."""
        results = []
        text = soup.get_text()

        # Look for date patterns like "12.03.2026" or "12 marca 2026"
        date_pattern = re.compile(r'(\d{1,2})[./](\d{1,2})[./](\d{4})')
        for match in date_pattern.finditer(text):
            try:
                day, month, year = int(match.group(1)), int(match.group(2)), int(match.group(3))
                specific_date = date_type(year, month, day)
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
    # POZ via Firecrawl (JetTable JS rendering)
    # ==========================================

    async def scrape_poz(self) -> list[dict]:
        """Scrape POZ schedule using Firecrawl (handles JS-rendered JetTable)."""
        url = f"{self.BASE_URL}/poradnie/"
        results = []

        try:
            data = await firecrawl_client.scrape_page(
                url, formats=["markdown", "html"]
            )
            if not data:
                logger.warning("  ⚠ POZ: Firecrawl returned no data")
                return results

            # Parse markdown table for POZ data
            markdown = data.get("markdown", "")
            html_content = data.get("html", "")

            # Try markdown parsing first
            results = self._parse_poz_markdown(markdown)

            # Fallback to HTML if markdown didn't yield results
            if not results and html_content:
                results = self._parse_poz_html(html_content)

            logger.info(f"  ✓ POZ: {len(results)} schedule entries")

        except Exception as e:
            logger.error(f"  ✗ Error scraping POZ: {e}")

        return results

    def _parse_poz_markdown(self, markdown: str) -> list[dict]:
        """Parse POZ schedule from Firecrawl markdown output."""
        results = []
        lines = markdown.split("\n")
        url = f"{self.BASE_URL}/poradnie/"

        current_doctor = None
        current_role = None

        for line in lines:
            line = line.strip()
            if not line:
                continue

            # Check if line has a day name and hours
            day_idx = parse_day_name(line)
            h_from, h_to = parse_hours(line)

            if day_idx is not None and h_from:
                results.append({
                    "clinic_name": "POZ",
                    "doctor_name": current_doctor,
                    "doctor_role": current_role,
                    "day_of_week": day_idx,
                    "specific_date": None,
                    "hours_from": h_from,
                    "hours_to": h_to,
                    "notes": None,
                    "source_url": url,
                })
            elif "|" in line:
                # Markdown table row
                cells = [c.strip() for c in line.split("|") if c.strip()]
                if len(cells) >= 2 and cells[0] not in ("---", "Dzień", "Lekarz", ""):
                    for cell in cells:
                        d = parse_day_name(cell)
                        if d is not None:
                            day_idx = d
                        hf, ht = parse_hours(cell)
                        if hf:
                            h_from, h_to = hf, ht

                    # Check for doctor name in cells
                    for cell in cells:
                        if parse_day_name(cell) is None and not re.search(r'\d{1,2}:\d{2}', cell.replace(".", ":")):
                            if len(cell) > 3 and cell not in ("---", "Dzień", "Godziny", "Lekarz"):
                                if "dr" in cell.lower() or "lek" in cell.lower() or len(cell) > 10:
                                    current_doctor = cell
                                else:
                                    current_role = cell

                    if day_idx is not None and h_from:
                        results.append({
                            "clinic_name": "POZ",
                            "doctor_name": current_doctor,
                            "doctor_role": current_role,
                            "day_of_week": day_idx,
                            "specific_date": None,
                            "hours_from": h_from,
                            "hours_to": h_to,
                            "notes": None,
                            "source_url": url,
                        })

        return results

    def _parse_poz_html(self, html: str) -> list[dict]:
        """Parse POZ schedule from Firecrawl HTML output (fallback)."""
        results = []
        url = f"{self.BASE_URL}/poradnie/"
        soup = BeautifulSoup(html, "html.parser")

        tables = soup.find_all("table")
        for table in tables:
            rows = table.find_all("tr")
            current_doctor = None
            for row in rows:
                cells = row.find_all(["td", "th"])
                cell_texts = [c.get_text(strip=True) for c in cells]

                if len(cell_texts) < 2:
                    continue

                day_idx = None
                h_from = h_to = None

                for text in cell_texts:
                    d = parse_day_name(text)
                    if d is not None:
                        day_idx = d
                    hf, ht = parse_hours(text)
                    if hf:
                        h_from, h_to = hf, ht
                    if "dr" in text.lower() or "lek." in text.lower():
                        current_doctor = text

                if day_idx is not None and h_from:
                    results.append({
                        "clinic_name": "POZ",
                        "doctor_name": current_doctor,
                        "doctor_role": "med. rodzinna",
                        "day_of_week": day_idx,
                        "specific_date": None,
                        "hours_from": h_from,
                        "hours_to": h_to,
                        "notes": None,
                        "source_url": url,
                    })

        return results

    # ==========================================
    # Pharmacy duties
    # ==========================================

    async def scrape_pharmacy_duty(self) -> list[dict]:
        """Scrape pharmacy duty schedules from mojedzialdowo.pl."""
        results = []

        try:
            response = await self.client.get(self.PHARMACY_URL)
            response.raise_for_status()
            soup = BeautifulSoup(response.text, "html.parser")

            # Parse pharmacy information from page content
            text_content = soup.get_text()
            current_year = datetime.now().year

            # Known pharmacies - extract from page or hardcode known data
            # mojedzialdowo.pl has a simple list format
            pharmacies_data = self._extract_pharmacies_from_page(soup, current_year)
            if pharmacies_data:
                results.extend(pharmacies_data)

            # Fallback: if scraping yields nothing, use known data
            if not results:
                results = self._get_known_pharmacy_data(current_year)

            logger.info(f"  ✓ Apteki: {len(results)} duty entries")

        except Exception as e:
            logger.error(f"  ✗ Error scraping pharmacies: {e}")
            results = self._get_known_pharmacy_data(datetime.now().year)

        return results

    def _extract_pharmacies_from_page(self, soup: BeautifulSoup, year: int) -> list[dict]:
        """Try to extract pharmacy data from HTML."""
        results = []
        # Look for structured data (tables, lists, divs with pharmacy info)
        content = soup.find("article") or soup.find("div", class_="entry-content") or soup
        text = content.get_text()

        # Pattern: pharmacy name, address, phone, hours
        # This varies by page structure, so we try common patterns
        blocks = content.find_all(["p", "li", "div"])
        current_pharmacy = None
        current_address = None
        current_phone = None

        for block in blocks:
            block_text = block.get_text(strip=True)
            if not block_text:
                continue

            # Detect pharmacy name (usually has "Apteka" in it)
            if "apteka" in block_text.lower():
                current_pharmacy = block_text
                continue

            # Detect address (ul., ulica)
            if "ul." in block_text.lower() or "ulica" in block_text.lower():
                current_address = block_text
                continue

            # Detect phone
            phone_match = re.search(r'(?:tel[.:]?\s*)?(\(?\d{2,3}\)?\s*\d{3}[-\s]?\d{2}[-\s]?\d{2})', block_text)
            if phone_match:
                current_phone = phone_match.group(1)

            # Detect hours
            h_from, h_to = parse_hours(block_text)
            if h_from and current_pharmacy:
                duty_type = "weekday"
                if any(w in block_text.lower() for w in ["sobota", "niedziela", "świąt", "swiat"]):
                    duty_type = "weekend"

                results.append({
                    "pharmacy_name": current_pharmacy,
                    "address": current_address or "",
                    "phone": current_phone,
                    "duty_type": duty_type,
                    "day_of_week": None,
                    "specific_dates": None,
                    "hours_from": h_from,
                    "hours_to": h_to,
                    "valid_year": year,
                    "notes": None,
                })

        return results

    def _get_known_pharmacy_data(self, year: int) -> list[dict]:
        """Fallback: known pharmacy duty data for powiat dzialdowski."""
        return [
            # Apteka MANADA II - Działdowo
            {
                "pharmacy_name": "Apteka MANADA II",
                "address": "ul. Leśna 13d, 13-200 Działdowo",
                "phone": "(23) 697-95-16",
                "duty_type": "weekday",
                "day_of_week": None,  # Pn-Sob
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
                "day_of_week": 6,  # Niedziela
                "specific_dates": None,
                "hours_from": "12:00",
                "hours_to": "21:00",
                "valid_year": year,
                "notes": "Dyżur niedzielny 12:00-21:00",
            },
            # Apteka Solaris - Iłowo-Osada
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
    # Main scrape-all method
    # ==========================================

    async def scrape_all_clinics(self) -> list[dict]:
        """Scrape all clinic schedules (static + POZ via Firecrawl)."""
        all_results = []

        # 1. Static clinics (httpx + BeautifulSoup)
        for name, path in self.CLINIC_URLS.items():
            entries = await self.scrape_static_clinic(name, path)
            all_results.extend(entries)

        # 2. POZ via Firecrawl
        poz_entries = await self.scrape_poz()
        all_results.extend(poz_entries)

        logger.info(f"Total clinic entries: {len(all_results)}")
        return all_results

    async def scrape_all(self) -> tuple[list[dict], list[dict]]:
        """Scrape everything: clinics + pharmacies."""
        clinics = await self.scrape_all_clinics()
        pharmacies = await self.scrape_pharmacy_duty()
        return clinics, pharmacies
