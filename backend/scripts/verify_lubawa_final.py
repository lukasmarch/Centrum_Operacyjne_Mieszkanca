import requests
from bs4 import BeautifulSoup

def check_biletyna_lubawa():
    # Try different variations
    urls = [
        "https://biletyna.pl/miejsce/Kino-Pokoj-Lubawa",
        "https://biletyna.pl/kino/Kino-Pokoj-Lubawa",
        "https://biletyna.pl/film/Lubawa"
    ]
    
    headers = { 'User-Agent': 'Mozilla/5.0' }
    
    for url in urls:
        print(f"Checking {url}...")
        try:
            r = requests.get(url, headers=headers, allow_redirects=True)
            print(f"Final URL: {r.url}")
            print(f"Status: {r.status_code}")
            soup = BeautifulSoup(r.text, 'html.parser')
            
            # Check for specific movie known to be playing
            if "Pomoc domowa" in soup.get_text():
                print("FOUND 'Pomoc domowa'!")
                
                # Check for hours/dates
                dates = soup.select('.event-date')
                print(f"Found {len(dates)} .event-date elements.")
            else:
                print("Did NOT find 'Pomoc domowa'.")
                
            print("-" * 20)
            
        except Exception as e:
            print(e)

if __name__ == "__main__":
    check_biletyna_lubawa()
