import requests
from bs4 import BeautifulSoup

def check_coigdzie():
    url = "https://kino.coigdzie.pl/miasto/Lubawa"
    print(f"Checking {url}...")
    headers = { 
        'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
    }
    try:
        r = requests.get(url, headers=headers)
        print(f"Status: {r.status_code}")
        
        soup = BeautifulSoup(r.text, 'html.parser')
        
        # Coigdzie usually lists movies in rows or cards
        # Look for titles
        # Structure often: .repertoire-movie or .element
        
        # Let's verify common classes
        movies = soup.select('.repertoire-movie')
        if not movies:
             movies = soup.select('.element') # generic
        if not movies:
             movies = soup.select('.movie-repertoire')

        print(f"Found {len(movies)} movie blocks.")
        
        for m in movies:
            title_el = m.select_one('.title') or m.select_one('h2') or m.select_one('h3')
            title = title_el.get_text(strip=True) if title_el else "No title"
            
            hours = m.select('.hour')
            # or .time
            if not hours:
                hours = m.select('.times a')
                
            times = [h.get_text(strip=True) for h in hours]
            
            print(f"Movie: {title} | Times: {times}")

        # Check raw text if classes fail
        if not movies:
            print("No movie blocks found. Dumping a bit of text:")
            print(soup.get_text()[:500])

    except Exception as e:
        print(e)

if __name__ == "__main__":
    check_coigdzie()
