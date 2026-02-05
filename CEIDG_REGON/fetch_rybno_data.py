from regon_client import RegonClient
import requests
import xml.etree.ElementTree as ET

API_KEY = "b220c4e85a1b4e1da8b8"

WOJ = "28"
POW = "03"
GM = "06" 

def main():
    print("Connecting to REGON API (PROD)...")
    client = RegonClient(api_key=API_KEY, env='PRODUKCJA')
    success, sid = client.login()
    if not success:
        print(f"Login failed: {sid}")
        return

    print(f"Logged in. SID: {sid}")

    # Test 6: Search GUS Regon (Control) vs Rybno Regon
    print(f"\n--- TEST: Search GUS Control (000331501) ---")
    body = f"""
        <ns:DaneSzukaj xmlns:dat="http://CIS/BIR/PUBL/2014/07/DataContract">
            <ns:pParametryWyszukiwania>
                <dat:Regon>000331501</dat:Regon>
            </ns:pParametryWyszukiwania>
        </ns:DaneSzukaj>
    """
    try:
        response = client._send_soap_request("DaneSzukaj", body)
        content = client._extract_xml_from_response(response.text)
        root = ET.fromstring(content)
        result_str = None
        for elem in root.iter():
            if elem.tag.endswith("Result") and elem.text:
                result_str = elem.text
                break
        
        if result_str:
            print("GUS RESULT FOUND!")
            print(result_str[:500])
        else:
            print("GUS Search FAILED (Empty Result).")

    except Exception as e:
        print(f"Exception: {e}")

    print(f"\n--- TEST: Search Rybno (510743322) ---")
    body = f"""
        <ns:DaneSzukaj xmlns:dat="http://CIS/BIR/PUBL/2014/07/DataContract">
            <ns:pParametryWyszukiwania>
                <dat:Regon>510743322</dat:Regon>
            </ns:pParametryWyszukiwania>
        </ns:DaneSzukaj>
    """
    try:
        response = client._send_soap_request("DaneSzukaj", body)
        content = client._extract_xml_from_response(response.text)
        root = ET.fromstring(content)
        result_str = None
        for elem in root.iter():
            if elem.tag.endswith("Result") and elem.text:
                result_str = elem.text
                break
        
        if result_str:
            print("RYBNO RESULT FOUND!")
            print(result_str[:500])
        else:
            print("RYBNO Search FAILED (Empty Result). Checks status:")
            # Status check
            body_stat = f"""<ns:GetValue xmlns:ns="http://CIS/BIR/2014/07"><ns:pNazwaParametru>KomunikatKod</ns:pNazwaParametru></ns:GetValue>"""
            action = 'http://CIS/BIR/2014/07/IUslugaBIR/GetValue'
            env = f"""<soap:Envelope xmlns:soap="http://www.w3.org/2003/05/soap-envelope" xmlns:ns="http://CIS/BIR/2014/07">
               <soap:Header xmlns:wsa="http://www.w3.org/2005/08/addressing"><wsa:Action>{action}</wsa:Action><wsa:To>{client.url}</wsa:To></soap:Header>
               <soap:Body>{body_stat}</soap:Body></soap:Envelope>"""
            resp = requests.post(client.url, data=env.encode('utf-8'), headers={'Content-Type': 'application/soap+xml; charset=utf-8', 'sid': sid})
            content = client._extract_xml_from_response(resp.text)
            print(f"Status Code: {content}")

    except Exception as e:
        print(f"Exception: {e}")
    
    # Test 7: Search by Name "URZĄD GMINY RYBNO"
    print(f"\n--- TEST: Search by Name 'URZĄD GMINY RYBNO' ---")
    body = f"""
        <ns:DaneSzukaj xmlns:dat="http://CIS/BIR/PUBL/2014/07/DataContract">
            <ns:pParametryWyszukiwania>
                <dat:Nazwa>URZĄD GMINY RYBNO</dat:Nazwa>
            </ns:pParametryWyszukiwania>
        </ns:DaneSzukaj>
    """
    try:
        response = client._send_soap_request("DaneSzukaj", body)
        content = client._extract_xml_from_response(response.text)
        root = ET.fromstring(content)
        result_str = None
        for elem in root.iter():
            if elem.tag.endswith("Result") and elem.text:
                result_str = elem.text
                break
        
        if result_str:
            print("NAME RESULT FOUND!")
            # Print simplified list
            inner = ET.fromstring(result_str)
            for item in inner.findall('dane'):
                 print(f"Name: {item.find('Nazwa').text} | Regon: {item.find('Regon').text} | Woj: {item.find('Wojewodztwo').text} | Pow: {item.find('Powiat').text} | Gm: {item.find('Gmina').text}")
        else:
            print("NAME Search FAILED (Empty Result). Checks status:")
             # Status check
            body_stat = f"""<ns:GetValue xmlns:ns="http://CIS/BIR/2014/07"><ns:pNazwaParametru>KomunikatKod</ns:pNazwaParametru></ns:GetValue>"""
            action = 'http://CIS/BIR/2014/07/IUslugaBIR/GetValue'
            env = f"""<soap:Envelope xmlns:soap="http://www.w3.org/2003/05/soap-envelope" xmlns:ns="http://CIS/BIR/2014/07">
               <soap:Header xmlns:wsa="http://www.w3.org/2005/08/addressing"><wsa:Action>{action}</wsa:Action><wsa:To>{client.url}</wsa:To></soap:Header>
               <soap:Body>{body_stat}</soap:Body></soap:Envelope>"""
            resp = requests.post(client.url, data=env.encode('utf-8'), headers={'Content-Type': 'application/soap+xml; charset=utf-8', 'sid': sid})
            content = client._extract_xml_from_response(resp.text)
            print(f"Status Code: {content}")


    except Exception as e:
        print(f"Exception: {e}")

if __name__ == "__main__":
    main()

