import requests
import xml.etree.ElementTree as ET

class RegonClient:
    ENVIRONMENTS = {
        'PRODUKCJA': 'https://wyszukiwarkaregon.stat.gov.pl/wsBIR/UslugaBIRzewnPubl.svc',
        'TEST': 'https://wyszukiwarkaregontest.stat.gov.pl/wsBIR/UslugaBIRzewnPubl.svc'
    }

    def __init__(self, api_key, env='PRODUKCJA'):
        self.api_key = api_key
        self.url = self.ENVIRONMENTS.get(env, self.ENVIRONMENTS['PRODUKCJA'])
        self.sid = None
        self.ns = {
            'soap': "http://www.w3.org/2003/05/soap-envelope",
            'ns': "http://CIS/BIR/PUBL/2014/07",
            'wsa': "http://www.w3.org/2005/08/addressing"
        }

    def _get_headers(self, action):
        headers = {
            'Content-Type': 'application/soap+xml; charset=utf-8',
        }
        if self.sid:
            headers['sid'] = self.sid
        return headers

    def _send_soap_request(self, action, body_content):
        # SOAP 1.2 Envelope
        envelope = f"""<soap:Envelope xmlns:soap="http://www.w3.org/2003/05/soap-envelope" xmlns:ns="http://CIS/BIR/PUBL/2014/07">
           <soap:Header xmlns:wsa="http://www.w3.org/2005/08/addressing">
              <wsa:Action>http://CIS/BIR/PUBL/2014/07/IUslugaBIRzewnPubl/{action}</wsa:Action>
              <wsa:To>{self.url}</wsa:To>
           </soap:Header>
           <soap:Body>
              {body_content}
           </soap:Body>
        </soap:Envelope>"""
        
        response = requests.post(
            self.url, 
            data=envelope.encode('utf-8'), 
            headers=self._get_headers(action)
        )
        return response

    def _extract_xml_from_response(self, content):
        if "--uuid:" in content:
            try:
                start = content.find("<s:Envelope")
                if start == -1:
                     start = content.find("<soap:Envelope")
                
                end = content.find("</s:Envelope>") + len("</s:Envelope>")
                if end == -1 + len("</s:Envelope>"):
                     end = content.find("</soap:Envelope>") + len("</soap:Envelope>")
                
                if start != -1 and end != -1:
                    return content[start:end]
            except:
                pass 
        return content

    def login(self):
        body = f"""
            <ns:Zaloguj>
                <ns:pKluczUzytkownika>{self.api_key}</ns:pKluczUzytkownika>
            </ns:Zaloguj>
        """
        response = self._send_soap_request('Zaloguj', body)
        
        if response.status_code == 200:
            try:
                content = self._extract_xml_from_response(response.text)
                root = ET.fromstring(content)
                
                sid = None
                for elem in root.iter():
                    if elem.tag.endswith('ZalogujResult'):
                        sid = elem.text
                        break
                
                if sid:
                    self.sid = sid
                    return True, self.sid
                else:
                    return False, "Empty SID received"
            except Exception as e:
                # print(f"DEBUG: Response Content: {response.text}")
                return False, f"XML Parsing error: {str(e)}"
        else:
            # print(f"DEBUG: HTTP Status: {response.status_code}")
            # print(f"DEBUG: Response Content: {response.text}")
            return False, f"HTTP Error {response.status_code}: {response.text}"

    def logout(self):
        if not self.sid:
            return True
        
        body = f"""
            <ns:Wyloguj>
                <ns:pIdentyfikatorSesji>{self.sid}</ns:pIdentyfikatorSesji>
            </ns:Wyloguj>
        """
        self._send_soap_request('Wyloguj', body)
        self.sid = None
        return True

    def search_by_teryt(self, woj, pow, gm):
        """
        Search for entities by TERYT codes (Wojewodztwo, Powiat, Gmina).
        """
        if not self.sid:
             raise Exception("Not logged in. Call login() first.")
        
        # Validated namespace format using 'dat' prefix for DataContract
        body = f"""
            <ns:DaneSzukaj xmlns:dat="http://CIS/BIR/PUBL/2014/07/DataContract">
                <ns:pParametryWyszukiwania>
                    <dat:AdsSymbolWojewodztwa>{woj}</dat:AdsSymbolWojewodztwa>
                    <dat:AdsSymbolPowiatu>{pow}</dat:AdsSymbolPowiatu>
                    <dat:AdsSymbolGminy>{gm}</dat:AdsSymbolGminy>
                </ns:pParametryWyszukiwania>
            </ns:DaneSzukaj>
        """
        
        response = self._send_soap_request('DaneSzukaj', body)
        return self._parse_search_response(response)

    def search_by_regon(self, regon):
        """
        Search for entity by REGON.
        """
        if not self.sid:
             raise Exception("Not logged in. Call login() first.")
        
        body = f"""
            <ns:DaneSzukaj xmlns:dat="http://CIS/BIR/PUBL/2014/07/DataContract">
                <ns:pParametryWyszukiwania>
                    <dat:Regon>{regon}</dat:Regon>
                </ns:pParametryWyszukiwania>
            </ns:DaneSzukaj>
        """
        response = self._send_soap_request('DaneSzukaj', body)
        return self._parse_search_response(response)

    def search_by_nip(self, nip):
        """
        Search for entity by NIP.
        """
        if not self.sid:
             raise Exception("Not logged in. Call login() first.")
        
        body = f"""
            <ns:DaneSzukaj xmlns:dat="http://CIS/BIR/PUBL/2014/07/DataContract">
                <ns:pParametryWyszukiwania>
                    <dat:Nip>{nip}</dat:Nip>
                </ns:pParametryWyszukiwania>
            </ns:DaneSzukaj>
        """
        response = self._send_soap_request('DaneSzukaj', body)
        return self._parse_search_response(response)

    def _parse_search_response(self, response):
        if response.status_code == 200:
            content = self._extract_xml_from_response(response.text)
            print(f"DEBUG RAW CONTENT: {content[:500]}")
            root = ET.fromstring(content)
            
            # The result is inside DaneSzukajResult which contains another XML string!
            # We need to parse that inner XML.
            
            search_result_xml = None
            for elem in root.iter():
               if elem.tag.endswith('DaneSzukajResult') and elem.text:
                   search_result_xml = elem.text
                   break
            
            if search_result_xml:
                # Parse the inner XML which has the list of entities
                # Inner XML structure: <root><dane>...</dane><dane>...</dane></root>
                try:
                    inner_root = ET.fromstring(search_result_xml)
                    results = []
                    for dane in inner_root.findall('dane'):
                        entity = {}
                        for child in dane:
                             # Tag might be namespaced or not, usually simple tag in inner xml
                            tag = child.tag
                            entity[tag] = child.text
                        results.append(entity)
                    return results
                except Exception as e:
                    print(f"Error parsing inner XML: {e}")
                    return None
            else:
                return [] # No results found
        else:
             print(f"Error {response.status_code}: {response.text}")
             return None
        return None

    def get_full_report(self, regon, report_name):
        if not self.sid:
             raise Exception("Not logged in.")

        body = f"""
            <ns:DanePobierzPelnyRaport>
                <ns:pRegon>{regon}</ns:pRegon>
                <ns:pNazwaRaportu>{report_name}</ns:pNazwaRaportu>
            </ns:DanePobierzPelnyRaport>
        """
        response = self._send_soap_request('DanePobierzPelnyRaport', body)
        # Extract XML envelope first
        content = self._extract_xml_from_response(response.text)
        
        # Then extract the inner result which is likely inside DanePobierzPelnyRaportResult
        # But for now just return the cleaned envelope content for the calling script to handle or debug.
        # Actually, let's try to extract the inner text if possible to match search_by_teryt style?
        # But fetching script expects raw XML string to save.
        return content
