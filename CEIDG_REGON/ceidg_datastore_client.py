"""
CEIDG DataStore SOAP Client
Pobiera dane o firmach z Centralnej Ewidencji i Informacji o Działalności Gospodarczej
Używa SOAP API DataStore z obsługą wyszukiwania po gminie

API Endpoint: https://datastore.ceidg.gov.pl/CEIDG.DataStore/services/DataStoreProvider201901.svc
"""

import requests
import xml.etree.ElementTree as ET
from typing import Optional, List, Dict, Any
import json
import os
from datetime import datetime
import time

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


class CEIDGDataStoreClient:
    """Client for CEIDG DataStore SOAP API"""
    
    PROD_URL = "https://datastore.ceidg.gov.pl/CEIDG.DataStore/services/DataStoreProvider201901.svc"
    TEST_URL = "https://datastoretest.ceidg.gov.pl/CEIDG.DataStore/services/DataStoreProvider201901.svc"
    
    # Namespace for SOAP
    NS = "http://tempuri.org/"
    
    def __init__(self, auth_token: str, test_mode: bool = False):
        """
        Initialize CEIDG DataStore client.
        
        Args:
            auth_token: Authentication token from CEIDG
            test_mode: Use test environment if True
        """
        self.url = self.TEST_URL if test_mode else self.PROD_URL
        self.auth_token = auth_token
        self.headers = {
            "Content-Type": "application/soap+xml; charset=utf-8"
        }
    
    def _create_soap_envelope(self, method: str, params: Dict[str, str]) -> str:
        """Create SOAP envelope for request."""
        params_xml = "\n".join([f"<ns:{k}>{v}</ns:{k}>" for k, v in params.items()])
        
        return f'''<?xml version="1.0" encoding="utf-8"?>
<soap:Envelope xmlns:soap="http://www.w3.org/2003/05/soap-envelope" xmlns:ns="{self.NS}">
  <soap:Header/>
  <soap:Body>
    <ns:{method}>
      <ns:AuthToken>{self.auth_token}</ns:AuthToken>
      {params_xml}
    </ns:{method}>
  </soap:Body>
</soap:Envelope>'''
    
    def _send_request(self, method: str, params: Dict[str, str], timeout: int = 60) -> str:
        """Send SOAP request and return response text."""
        envelope = self._create_soap_envelope(method, params)
        
        try:
            response = requests.post(
                self.url,
                data=envelope.encode('utf-8'),
                headers=self.headers,
                timeout=timeout
            )
            return response.text
        except requests.exceptions.Timeout:
            raise Exception(f"Request timeout after {timeout}s")
        except requests.exceptions.RequestException as e:
            raise Exception(f"Request failed: {e}")
    
    def get_by_nip(self, nip: str) -> Optional[Dict[str, Any]]:
        """
        Get company data by NIP.
        
        Args:
            nip: Company NIP number
            
        Returns:
            Company data dict or None
        """
        response = self._send_request("GetMigrationData201901", {"NIP": nip})
        return self._parse_response(response)
    
    def search_by_commune(self, commune: str, date_from: str = None) -> List[Dict[str, Any]]:
        """
        Search for businesses in a specific commune (gmina).
        
        Args:
            commune: Name of the commune (e.g., "Rybno")
            date_from: Optional date filter (YYYY-MM-DD)
            
        Returns:
            List of business data dicts
        """
        params = {"Commune": commune}
        if date_from:
            params["DateFrom"] = date_from
            
        response = self._send_request("GetMigrationData201901", params)
        return self._parse_response(response)
    
    def _parse_response(self, response_text: str) -> Any:
        """Parse SOAP response and extract data."""
        if not response_text:
            return None
            
        try:
            # Handle potential encoding issues
            response_text = response_text.replace('&lt;', '<').replace('&gt;', '>').replace('&amp;', '&')
            
            root = ET.fromstring(response_text)
            
            # Find the result element
            for elem in root.iter():
                if 'GetMigrationData201901Result' in elem.tag or 'Result' in elem.tag:
                    if elem.text:
                        # Result might be embedded XML
                        try:
                            inner = ET.fromstring(elem.text)
                            return self._extract_companies(inner)
                        except:
                            return elem.text
            
            return None
        except ET.ParseError as e:
            print(f"XML Parse Error: {e}")
            print(f"Response: {response_text[:500]}")
            return None
    
    def _extract_companies(self, root: ET.Element) -> List[Dict[str, Any]]:
        """Extract company data from parsed XML."""
        companies = []
        
        for company in root.iter():
            if company.tag.lower() in ['przedsiebiorca', 'firma', 'entry']:
                data = {}
                for child in company:
                    tag = child.tag.split('}')[-1] if '}' in child.tag else child.tag
                    data[tag] = child.text
                if data:
                    companies.append(data)
        
        return companies


def extract_business_info(firma: Dict[str, Any]) -> Dict[str, Any]:
    """Extract key information from CEIDG firm data."""
    return {
        "nazwa": firma.get("Nazwa", firma.get("nazwa", "")),
        "nip": firma.get("NIP", firma.get("nip", "")),
        "regon": firma.get("REGON", firma.get("regon", "")),
        "status": firma.get("Status", firma.get("status", "")),
        "dataRozpoczecia": firma.get("DataRozpoczeciaDzialalnosci", ""),
        "adres": {
            "ulica": firma.get("Ulica", ""),
            "nrBudynku": firma.get("Budynek", ""),
            "miejscowosc": firma.get("Miejscowosc", ""),
            "kodPocztowy": firma.get("KodPocztowy", ""),
            "gmina": firma.get("Gmina", ""),
            "powiat": firma.get("Powiat", ""),
            "wojewodztwo": firma.get("Wojewodztwo", "")
        },
        "pkdGlowne": {
            "kod": firma.get("PKDGlowny", ""),
            "nazwa": ""
        },
        "email": firma.get("Email", ""),
        "telefon": firma.get("Telefon", ""),
        "www": firma.get("WWW", "")
    }


# PKD Section names
PKD_SECTIONS = {
    "A": "Rolnictwo, leśnictwo, łowiectwo i rybactwo",
    "B": "Górnictwo i wydobywanie",
    "C": "Przetwórstwo przemysłowe",
    "D": "Wytwarzanie i zaopatrywanie w energię",
    "E": "Dostawa wody; gospodarowanie ściekami",
    "F": "Budownictwo",
    "G": "Handel hurtowy i detaliczny",
    "H": "Transport i gospodarka magazynowa",
    "I": "Działalność związana z zakwaterowaniem i usługami gastronomicznymi",
    "J": "Informacja i komunikacja",
    "K": "Działalność finansowa i ubezpieczeniowa",
    "L": "Działalność związana z obsługą rynku nieruchomości",
    "M": "Działalność profesjonalna, naukowa i techniczna",
    "N": "Działalność w zakresie usług administrowania",
    "O": "Administracja publiczna i obrona narodowa",
    "P": "Edukacja",
    "Q": "Opieka zdrowotna i pomoc społeczna",
    "R": "Działalność związana z kulturą, rozrywką i rekreacją",
    "S": "Pozostała działalność usługowa",
    "T": "Gospodarstwa domowe zatrudniające pracowników",
    "U": "Organizacje i zespoły eksterytorialne"
}


if __name__ == "__main__":
    # Test
    token = os.environ.get("CEIDG_API_TOKEN")
    if not token:
        print("Set CEIDG_API_TOKEN in .env file")
    else:
        print(f"Token loaded (length: {len(token)})")
        client = CEIDGDataStoreClient(auth_token=token)
        
        print("Testing NIP search...")
        try:
            result = client.get_by_nip("5711567815")
            print(f"Result: {result}")
        except Exception as e:
            print(f"Error: {e}")
