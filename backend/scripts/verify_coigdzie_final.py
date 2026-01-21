import requests
from bs4 import BeautifulSoup

def check_coigdzie_cinema():
    # URL from user suggestion/Google: https://kino.coigdzie.pl/repertuar_kina/Kino_Pokoj_w_Lubawie
    # Or just try finding the cinema link
    url = "https://kino.coigdzie.pl/miasto/Lubawa"
    
    # Try the city page again with more aggressive headers/cookies if needed
    # But let's try direct cinema URL if possible
    # Google result: http://kino.coigdzie.pl/kino/Kino_Pokoj_w_Lubawie
    
    url_cinema = "https://kino.coigdzie.pl/kino/Kino_Pokoj_w_Lubawie"
    print(f"Checking {url_cinema}...")
    headers = { 
        'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
    }
    try:
        r = requests.get(url_cinema, headers=headers)
        print(f"Status: {r.status_code}")
        soup = BeautifulSoup(r.text, 'html.parser')
        
        # Look for movies
        # Structure on Coigdzie usually involves .repertoire-movie or similar
        movies = soup.select('.repertoire-movie') 
        if not movies:
             # Try listing all divs with class
             divs = soup.find_all("div", class_=True)
             classes = set()
             for d in divs:
                 classes.update(d['class'])
             print(f"Classes found: {list(classes)[:10]}")
             
        print(f"Found {len(movies)} movies.")
        for m in movies:
             title = m.select_one('.title').get_text(strip=True)
             print(f"Title: {title}")
             # Times?
             
    except Exception as e:
        print(e)

if __name__ == "__main__":
    check_coigdzie_cinema()
