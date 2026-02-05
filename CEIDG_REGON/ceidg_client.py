"""
CEIDG API v3 Client
Pobiera dane o firmach z Centralnej Ewidencji i Informacji o Działalności Gospodarczej

API Docs: https://dane.biznes.gov.pl/api/ceidg/v3
Endpoint: /firmy - zwraca listę firm na podstawie kryteriów wyszukiwania
"""

import requests
from typing import Optional, List, Dict, Any
import json
import os
from datetime import datetime

# Load .env file if exists
def load_env():
    env_path = os.path.join(os.path.dirname(__file__), '.env')
    if os.path.exists(env_path):
        with open(env_path, 'r') as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith('#') and '=' in line:
                    key, value = line.split('=', 1)
                    # Remove quotes if present
                    value = value.strip().strip("'").strip('"')
                    os.environ[key.strip()] = value

load_env()


class CEIDGClient:
    """Client for CEIDG REST API v3"""
    
    PROD_URL = "https://dane.biznes.gov.pl/api/ceidg/v3"
    TEST_URL = "https://test-dane.biznes.gov.pl/api/ceidg/v3"
    
    def __init__(self, api_token: str, test_mode: bool = False):
        """
        Initialize CEIDG client.
        
        Args:
            api_token: JWT token from biznes.gov.pl
            test_mode: Use test environment if True
        """
        self.base_url = self.TEST_URL if test_mode else self.PROD_URL
        self.headers = {
            "Authorization": f"Bearer {api_token}",
            "Accept": "application/json"
        }
    
    def search_by_gmina(self, gmina: str, limit: int = 25, page: int = 1, 
                        status: List[str] = None) -> Dict[str, Any]:
        """
        Search for businesses in a specific gmina.
        
        Args:
            gmina: Name of the gmina (e.g., "Rybno")
            limit: Results per page (max 25)
            page: Page number (starts from 1)
            status: List of statuses to filter (AKTYWNY, WYKRESLONY, ZAWIESZONY, etc.)
            
        Returns:
            Dict with 'firmy' list, 'count', and 'links' for pagination
        """
        params = {
            "gmina": gmina,
            "limit": min(limit, 25),
            "page": page
        }
        
        # Add status filters if provided
        if status:
            params["status"] = status
        
        response = requests.get(
            f"{self.base_url}/firmy",
            headers=self.headers,
            params=params,
            timeout=30
        )
        
        if response.status_code == 200:
            return response.json()
        elif response.status_code == 204:
            return {"firmy": [], "count": 0, "links": {}}
        elif response.status_code == 401:
            raise Exception("CEIDG API Error 401: Brak autoryzacji - sprawdź token JWT")
        elif response.status_code == 429:
            raise Exception("CEIDG API Error 429: Zbyt wiele zapytań - limit przekroczony")
        else:
            raise Exception(f"CEIDG API Error {response.status_code}: {response.text}")
    
    def search_by_nip(self, nip: str) -> Optional[Dict[str, Any]]:
        """
        Get company details by NIP.
        
        Args:
            nip: Company NIP number
            
        Returns:
            Company data dict or None if not found
        """
        response = requests.get(
            f"{self.base_url}/firmy",
            headers=self.headers,
            params={"nip": nip},
            timeout=30
        )
        
        if response.status_code == 200:
            data = response.json()
            firmy = data.get("firmy", [])
            return firmy[0] if firmy else None
        elif response.status_code == 204:
            return None
        else:
            raise Exception(f"CEIDG API Error {response.status_code}: {response.text}")
    
    def fetch_all_businesses_in_gmina(self, gmina: str, 
                                       statuses: List[str] = None) -> List[Dict[str, Any]]:
        """
        Fetch ALL businesses in a gmina (handles pagination).
        
        Args:
            gmina: Name of the gmina
            statuses: List of statuses to include (default: AKTYWNY only)
            
        Returns:
            List of all businesses
        """
        if statuses is None:
            statuses = ["AKTYWNY"]
        
        all_businesses = []
        page = 1
        
        while True:
            print(f"Fetching page {page}...")
            result = self.search_by_gmina(gmina, limit=25, page=page, status=statuses)
            
            firms = result.get("firmy", [])
            if not firms:
                break
                
            all_businesses.extend(firms)
            
            # Check if there are more pages
            total_count = result.get("count", 0)
            print(f"  Found {len(firms)} firms (total: {total_count})")
            
            # Check for next page in links
            links = result.get("links", {})
            if not links.get("next") or page * 25 >= total_count:
                break
                
            page += 1
        
        print(f"Total businesses found: {len(all_businesses)}")
        return all_businesses


def extract_business_info(firma: Dict[str, Any]) -> Dict[str, Any]:
    """
    Extract key information from CEIDG firm data.
    
    Args:
        firma: Raw firm data from API
        
    Returns:
        Simplified business info dict
    """
    # Get main address
    adres = firma.get("adresDzialalnosci", {})
    
    # Get owner info
    wlasciciel = firma.get("wlasciciel", {})
    
    return {
        "id": firma.get("id", ""),
        "nazwa": firma.get("nazwa", ""),
        "nip": wlasciciel.get("nip", ""),
        "regon": wlasciciel.get("regon", ""),
        "status": firma.get("status", ""),
        "dataRozpoczecia": firma.get("dataRozpoczecia", ""),
        "wlasciciel": {
            "imie": wlasciciel.get("imie", ""),
            "nazwisko": wlasciciel.get("nazwisko", "")
        },
        "adres": {
            "ulica": adres.get("ulica", ""),
            "budynek": adres.get("budynek", ""),
            "lokal": adres.get("lokal", ""),
            "miasto": adres.get("miasto", ""),
            "kod": adres.get("kod", ""),
            "gmina": adres.get("gmina", ""),
            "powiat": adres.get("powiat", ""),
            "wojewodztwo": adres.get("wojewodztwo", ""),
            "terc": adres.get("terc", ""),
            "simc": adres.get("simc", "")
        },
        "link": firma.get("link", "")
    }


def generate_statistics(businesses: List[Dict[str, Any]]) -> Dict[str, Any]:
    """
    Generate statistics from business list.
    
    Args:
        businesses: List of extracted business info
        
    Returns:
        Statistics dict
    """
    stats = {
        "total": len(businesses),
        "by_status": {},
        "by_miejscowosc": {}
    }
    
    for biz in businesses:
        # Count by status
        status = biz.get("status", "NIEZNANY")
        stats["by_status"][status] = stats["by_status"].get(status, 0) + 1
        
        # Count by miejscowosc
        miejscowosc = biz.get("adres", {}).get("miasto", "Nieznana")
        stats["by_miejscowosc"][miejscowosc] = stats["by_miejscowosc"].get(miejscowosc, 0) + 1
    
    return stats


if __name__ == "__main__":
    # Test with environment variable
    token = os.environ.get("CEIDG_API_TOKEN")
    if not token:
        print("Set CEIDG_API_TOKEN in .env file")
        print("Get your token at: https://biznes.gov.pl")
    else:
        print(f"Token loaded (length: {len(token)})")
        client = CEIDGClient(api_token=token)
        
        # Test NIP search first
        print("\nTesting NIP search for 5711567815...")
        try:
            result = client.search_by_nip("5711567815")
            if result:
                print(f"Found: {result.get('nazwa', 'N/A')}")
                print(f"Status: {result.get('status', 'N/A')}")
            else:
                print("Not found")
        except Exception as e:
            print(f"Error: {e}")
        
        # Test gmina search
        print("\nTesting gmina search for 'Rybno'...")
        try:
            result = client.search_by_gmina("Rybno", limit=5)
            count = result.get("count", 0)
            print(f"Total count: {count}")
            for firma in result.get("firmy", [])[:3]:
                print(f"  - {firma.get('nazwa', 'N/A')}")
        except Exception as e:
            print(f"Error: {e}")
