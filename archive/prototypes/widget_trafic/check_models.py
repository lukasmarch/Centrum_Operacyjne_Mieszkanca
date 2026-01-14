
import os
import sys

# Add backend directory to python path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from src.config import settings
from google import genai

def list_models():
    api_key = settings.GEMINI_API_KEY
    if not api_key:
        api_key = os.environ.get("GOOGLE_API_KEY")
    
    if not api_key:
        print("ERROR: No GEMINI_API_KEY or GOOGLE_API_KEY found in settings or environment.")
        return

    print(f"Using API Key: {api_key[:5]}...{api_key[-4:]}")

    try:
        client = genai.Client(api_key=api_key)
        print("Fetching available models...")
        
        # In google-genai SDK 0.x/1.x
        pager = client.models.list()
        
        found_flash = False
        print("\n--- Available Models ---")
        for model in pager:
            print(f"Name: {model.name}")
            print(f"Display Name: {model.display_name}")
            if 'flash' in model.name:
                found_flash = True
            print("-" * 20)
            
        if not found_flash:
            print("\nWARNING: No 'flash' models found.")

    except Exception as e:
        print(f"\nCRITICAL ERROR: {e}")

if __name__ == "__main__":
    list_models()
