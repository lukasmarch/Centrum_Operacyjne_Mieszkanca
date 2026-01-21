import requests
from bs4 import BeautifulSoup

def check_pagination():
    url = "https://biletyna.pl/film/Lubawa"
    print(f"Checking {url}...")
    headers = { 'User-Agent': 'Mozilla/5.0' }
    try:
        r = requests.get(url, headers=headers)
        soup = BeautifulSoup(r.text, 'html.parser')
        
        # Check for pagination controls
        pagination = soup.select('.pagination')
        if pagination:
            print("Found pagination.")
        else:
             print("No pagination found.")
        
        # Dump titles found
        titles = [t.get_text(strip=True) for t in soup.select('h3 a')]
        print(f"Titles found ({len(titles)}): {titles}")

    except Exception as e:
        print(e)

if __name__ == "__main__":
    check_pagination()
