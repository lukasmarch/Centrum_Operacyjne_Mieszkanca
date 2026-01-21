import requests
from bs4 import BeautifulSoup

def check_url(candidate):
    url = f"https://biletyna.pl/{candidate}"
    print(f"Checking {url}...")
    try:
        r = requests.get(url)
        print(f"Status: {r.status_code}")
        print(f"Effective URL: {r.url}")
        soup = BeautifulSoup(r.text, 'html.parser')
        title = soup.title.get_text(strip=True) if soup.title else "No Title"
        print(f"Page Title: {title}")
        
        # Check if generic list
        if "Biletyna.pl - bilety na wydarzenia" in title and len(title) < 40:
             print("Looks like generic home/list page.")
        
        # Check items count
        items = soup.select('.event-left-side')
        print(f"Items found: {len(items)}")
        
    except Exception as e:
        print(f"Error: {e}")
    print("-" * 20)

candidates = [
    "kino/Kino-Apollo-Dzialdowo",
    "kino/Kino-Apollo-w-Dzialdowie",
    "kino/MDK-Dzialdowo",
    "miejsce/Kino-Apollo-Dzialdowo",
    "kino/Kino-Pokoj-Lubawa",
    "kino/Kino-Pokoj-w-Lubawie",
    "miejsce/Kino-Pokoj-Lubawa"
]

if __name__ == "__main__":
    for c in candidates:
        check_url(c)
