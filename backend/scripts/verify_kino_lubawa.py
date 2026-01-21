import requests
from bs4 import BeautifulSoup
import re

def check_kino_lubawa():
    url = "https://kino.lubawa.pl/"
    print(f"Checking {url}...")
    headers = { 
        'User-Agent': 'Mozilla/5.0' 
    }
    
    try:
        r = requests.get(url, headers=headers, verify=False)
        r.encoding = 'utf-8' # Fix encoding
        
        soup = BeautifulSoup(r.text, 'html.parser')
        
        # Structure seems to be:
        # <h4>Title</h4>
        # ... <p>Date/Time</p> ...
        
        # Let's verify by finding all H4s and inspecting their next siblings
        h4s = soup.select('h4')
        print(f"Found {len(h4s)} h4 elements.")
        
        for h4 in h4s:
            title = h4.get_text(strip=True)
            print(f"Movie: {title}")
            
            # Times might be in the text following the h4, or in a sibling div/p
            # Let's inspect the parent or next siblings
            # Use next_elements or iterate siblings
            
            # Simple heuristic: look at the text of the parent container or close siblings
            # Often these sites are simple HTML streams
            
            parent_text = h4.parent.get_text(separator=' ')
            # Filter for times
            times = re.findall(r'(?<!\d)(\d{2}:\d{2})(?!\d)', parent_text)
            
            # This might capture times from other movies if they are in same container
            # We need to be specific.
            # Let's dump the parent structure to be sure
            print(f"Parent preview: {h4.parent.prettify()[:200]}")
            print(f"Times found in parent: {set(times)}")
            print("-" * 20)
                
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    check_kino_lubawa()
