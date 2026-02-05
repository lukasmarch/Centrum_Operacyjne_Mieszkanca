"""
Async client for REGON API (GUS)
Based on legacy regon_client.py logic but adapted for async/await and aiohttp.
"""
import aiohttp
import xml.etree.ElementTree as ET
from typing import Optional, Dict, List, Tuple, Any
from src.utils.logger import setup_logger
from src.config import settings

logger = setup_logger("RegonService")

class RegonService:
    """
    Async client for GUS REGON API (BIR1).
    """
    
    # Environments
    ENV_PROD = 'https://wyszukiwarkaregon.stat.gov.pl/wsBIR/UslugaBIRzewnPubl.svc'
    ENV_TEST = 'https://wyszukiwarkaregontest.stat.gov.pl/wsBIR/UslugaBIRzewnPubl.svc'
    
    def __init__(self, api_key: Optional[str] = None, use_test_env: bool = False):
        self.api_key = api_key or settings.REGON_API_KEY
        self.url = self.ENV_TEST if use_test_env else self.ENV_PROD
        self.sid: Optional[str] = None
        self.logger = logger
        
        if not self.api_key:
             self.logger.warning("REGON_API_KEY is not set. REGON queries will fail.")

    def _get_headers(self, action: str) -> Dict[str, str]:
        headers = {
            'Content-Type': 'application/soap+xml; charset=utf-8',
        }
        if self.sid:
            headers['sid'] = self.sid
        return headers

    def _build_envelope(self, action: str, body_content: str) -> str:
        return f"""<soap:Envelope xmlns:soap="http://www.w3.org/2003/05/soap-envelope" xmlns:ns="http://CIS/BIR/PUBL/2014/07">
           <soap:Header xmlns:wsa="http://www.w3.org/2005/08/addressing">
              <wsa:Action>http://CIS/BIR/PUBL/2014/07/IUslugaBIRzewnPubl/{action}</wsa:Action>
              <wsa:To>{self.url}</wsa:To>
           </soap:Header>
           <soap:Body>
              {body_content}
           </soap:Body>
        </soap:Envelope>"""

    async def _send_soap_request(self, action: str, body_content: str) -> str:
        envelope = self._build_envelope(action, body_content)
        
        async with aiohttp.ClientSession() as session:
            try:
                async with session.post(
                    self.url,
                    data=envelope.encode('utf-8'),
                    headers=self._get_headers(action)
                ) as response:
                    text = await response.text()
                    if response.status != 200:
                        self.logger.error(f"REGON API Error {response.status}: {text}")
                        raise Exception(f"REGON API HTTP {response.status}")
                    return text
            except Exception as e:
                self.logger.error(f"Request failed: {e}")
                raise

    def _extract_inner_xml(self, content: str, tag_suffix: str) -> Optional[str]:
        """Extracts text content from a specific XML tag ending with tag_suffix"""
        try:
            # Simple manual extraction to avoid complex namespace issues in first pass
            # Try to find content between <Tag>...</Tag>
            # Note: The response might be multipart/related or raw XML. 
            # We assume we get the XML part or can match text.
            
            # Using ElementTree for main structure
            # Remove potential multipart headers if present (not handling strictly here as aiohttp usually gives body)
            
            if "--uuid:" in content:
                # Basic cleanup if needed, similar to original client
                start = content.find("<s:Envelope") 
                if start == -1: start = content.find("<soap:Envelope")
                
                end = content.find("</s:Envelope>") + 13
                if end == 12: end = content.find("</soap:Envelope>") + 16
                
                if start != -1 and end != -1:
                    content = content[start:end]

            root = ET.fromstring(content)
            for elem in root.iter():
                if elem.tag.endswith(tag_suffix) and elem.text:
                    return elem.text
            return None
            
        except Exception as e:
            self.logger.error(f"XML Extraction error: {e}")
            return None

    async def login(self) -> bool:
        if not self.api_key:
            return False
            
        body = f"""
            <ns:Zaloguj>
                <ns:pKluczUzytkownika>{self.api_key}</ns:pKluczUzytkownika>
            </ns:Zaloguj>
        """
        try:
            response_text = await self._send_soap_request('Zaloguj', body)
            sid = self._extract_inner_xml(response_text, 'ZalogujResult')
            
            if sid:
                self.sid = sid
                return True
            else:
                self.logger.error("Login failed: No SID received")
                return False
        except Exception as e:
            self.logger.error(f"Login exception: {e}")
            return False

    async def logout(self):
        if not self.sid:
            return
            
        body = f"""
            <ns:Wyloguj>
                <ns:pIdentyfikatorSesji>{self.sid}</ns:pIdentyfikatorSesji>
            </ns:Wyloguj>
        """
        try:
            await self._send_soap_request('Wyloguj', body)
            self.sid = None
        except:
            pass

    async def search(self, nip: str = None, regon: str = None, name: str = None) -> List[Dict[str, str]]:
        """
        Search for entities. Automatically logs in if needed.
        """
        if not self.sid:
            if not await self.login():
                 raise Exception("Could not log in to REGON API")

        params_xml = ""
        if nip:
             params_xml = f"<dat:Nip>{nip.replace('-', '').replace(' ', '')}</dat:Nip>"
        elif regon:
             params_xml = f"<dat:Regon>{regon}</dat:Regon>"
        elif name:
             # Important: Encapsulate name for XML safety if needed, simplest is raw here
             params_xml = f"<dat:Nazwa>{name}</dat:Nazwa>"
        
        if not params_xml:
            return []

        body = f"""
            <ns:DaneSzukaj xmlns:dat="http://CIS/BIR/PUBL/2014/07/DataContract">
                <ns:pParametryWyszukiwania>
                    {params_xml}
                </ns:pParametryWyszukiwania>
            </ns:DaneSzukaj>
        """

        try:
            response_text = await self._send_soap_request('DaneSzukaj', body)
            result_xml_str = self._extract_inner_xml(response_text, 'DaneSzukajResult')
            
            if not result_xml_str:
                return []
                
            # Inner XML structure: <root><dane>...</dane><dane>...</dane></root>
            inner_root = ET.fromstring(result_xml_str)
            results = []
            
            for dane in inner_root.findall('dane'):
                entity = {}
                for child in dane:
                    entity[child.tag] = child.text
                results.append(entity)
                
            return results

        except Exception as e:
            self.logger.error(f"Search failed: {e}")
            return []
