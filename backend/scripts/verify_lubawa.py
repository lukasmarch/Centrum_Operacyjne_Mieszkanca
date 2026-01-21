import requests
from bs4 import BeautifulSoup

def check_filtered_url():
    url = "https://biletyna.pl/film/Pomoc-domowa/Lubawa"
    print(f"Checking {url}...")
    headers = { 'User-Agent': 'Mozilla/5.0' }
    try:
        r = requests.get(url, headers=headers)
        if r.status_code == 404:
             print("Status 404 - suffix didn't work.")
             return
             
        soup = BeautifulSoup(r.text, 'html.parser')
        
        dates = soup.select('.event-date')
        print(f"Found {len(dates)} .event-date elements.")
        
        # Check if today (15.01.2026) is present
        text = soup.get_text()
        if "15.01.2026" in text:
            print("Found 15.01.2026 in text.")
        else:
            print("Did NOT find 15.01.2026 in text.")

    except Exception as e:
        print(e)

if __name__ == "__main__":
    check_filtered_url()
