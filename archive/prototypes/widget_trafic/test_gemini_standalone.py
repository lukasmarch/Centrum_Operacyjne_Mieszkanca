
import os
import sys

# Try to find the backend .env file
current_dir = os.path.dirname(os.path.abspath(__file__))
backend_env_path = os.path.join(current_dir, '..', 'backend', '.env')

api_key = None

# Simple .env parser
if os.path.exists(backend_env_path):
    print(f"Loading env from {backend_env_path}")
    with open(backend_env_path, 'r') as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith('#'):
                continue
            if '=' in line:
                key, value = line.split('=', 1)
                if key.strip() == 'GEMINI_API_KEY':
                    api_key = value.strip()
                    break

if not api_key:
    # Fallback to env var if set
    api_key = os.environ.get("GEMINI_API_KEY")

if not api_key:
    print("ERROR: Could not find GEMINI_API_KEY in backend/.env or environment variables.")
    sys.exit(1)

print(f"API Key loaded: {api_key[:5]}...{api_key[-4:]}")

try:
    from google import genai
    from google.genai import types
except ImportError:
    print("Error: 'google-genai' package not found. Please run this script in an environment where it is installed.")
    print("Try: pip install google-genai")
    sys.exit(1)

def test_gemini():
    client = genai.Client(api_key=api_key)
    
    prompt = """
      Jesteś dyspozytorem ruchu dla regionu Rybno (powiat działdowski). 
      Twoim centrum jest miejscowość RYBNO. Sprawdź AKTUALNE (real-time) warunki drogowe i czasy przejazdu dla tras:
      1. Rybno -> Działdowo (DW538)
      2. Rybno -> Lubawa (DW538/DW541)
      3. Rybno -> Iława (przez Hartowiec)
      4. Rybno -> Olsztyn (najszybsza aktualna trasa)
      
      Zasady analizy:
      - Podaj AKTUALNY CZAS PRZEJAZDU (TravelTime) w minutach.
      - Opóźnienie (Delay) to różnica między czasem aktualnym a optymalnym.
      - W opisie ('NOTE') bądź ekstremalnie precyzyjny: jeśli jest zima, sprawdź czy przyczyną jest śliska nawierzchnia, błoto pośniegowe czy praca pługów. Jeśli to korek w małym mieście, określ czy to zator przy przejeździe kolejowym czy wzmożony ruch lokalny.
      - Opis musi być jednym, treściwym zdaniem, które wyjaśnia "dlaczego" (np. "Błoto pośniegowe na podjazdach pod wzniesienia spowalnia ruch ciężarowy").

      Format odpowiedzi:
      [ROUTE: Skąd-Dokąd | TIME: X min | STATUS: Status | DELAY: X min | NOTE: Opis przyczyny]
      
      Status values: Płynnie, Utrudnienia, Korki
    """
    model = "gemini-2.0-flash"

    print(f"\nSending request to model: {model}...")
    try:
        response = client.models.generate_content(
            model=model,
            contents=prompt,
             config=types.GenerateContentConfig(
                tools=[types.Tool(google_search=types.GoogleSearch())],
                response_modalities=["TEXT"],
            )
        )
        print("\n--- RESPONSE ---")
        print(response.text)
        print("----------------")
        
        # Test parsing logic
        import re
        text = response.text or ""
        pattern = r"\[ROUTE: (.*?) \| TIME: (.*?) \| STATUS: (.*?) \| DELAY: (.*?) \| NOTE: (.*?)\]"
        matches = re.finditer(pattern, text)
        found = False
        for i, match in enumerate(matches):
            found = True
            print(f"Match {i+1}: {match.group(1)} | {match.group(3)}")
            
        if not found:
            print("FAILURE: Regex did not match any lines.")
        else:
            print("SUCCESS: Parsing worked.")

    except Exception as e:
        print(f"\nERROR: API call failed.")
        print(e)

if __name__ == "__main__":
    test_gemini()
