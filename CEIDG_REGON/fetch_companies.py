from regon_client import RegonClient
import json

API_KEY = "b220c4e85a1b4e1da8b8"

# Gmina Rybno TERYT
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
    
    try:
        print(f"Searching for companies in Rybno ({WOJ} {POW} {GM})...")
        results = client.search_by_teryt(WOJ, POW, GM)
        
        if results:
            print(f"Found {len(results)} entities.")
            
            # Save to file
            filename = "rybno_companies.json"
            with open(filename, "w", encoding="utf-8") as f:
                json.dump(results, f, indent=4, ensure_ascii=False)
            print(f"Saved results to {filename}")
            
            # Print first 5
            for ent in results[:5]:
                print(f"- {ent.get('Nazwa', 'Unknown')} ({ent.get('Regon')}) - Typ: {ent.get('Typ')}")
                
        else:
            print("No entities found.")

    except Exception as e:
        print(f"Error: {e}")
    finally:
        client.logout()

if __name__ == "__main__":
    main()
