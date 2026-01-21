import requests
from bs4 import BeautifulSoup

def debug_coigdzie():
    url = "https://kino.coigdzie.pl/miasto/Lubawa"
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8',
        'Accept-Language': 'pl-PL,pl;q=0.9,en-US;q=0.8,en;q=0.7',
        'Referer': 'https://www.google.com/'
    }
    
    s = requests.Session()
    r = s.get(url, headers=headers)
    print(f"Status: {r.status_code}")
    print(f"Length: {len(r.text)}")
    
    if "Repertuar" in r.text:
       print("Page contains 'Repertuar'")
    
    soup = BeautifulSoup(r.text, 'html.parser')
    # Try finding any movie title known to be playing, e.g. "Pomoc domowa" or "Wielka"
    if "Pomoc domowa" in r.text:
        print("Found 'Pomoc domowa' in text")
    
    # Dump links
    links = soup.select('.repertoire-movie h3 a')
    print(f"Found {len(links)} movie links via .repertoire-movie h3 a")

if __name__ == "__main__":
    debug_coigdzie()
