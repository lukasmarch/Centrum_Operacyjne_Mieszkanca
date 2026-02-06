import os
import json
from firecrawl_client import FirecrawlClient
from parser import MarkdownParser

# Target URL
URL = "https://www.polskawliczbach.pl/gmina_Rybno_warminsko_mazurskie"

def main():
    # Check for API key
    api_key = os.getenv("FIRECRAWL_API_KEY")
    if not api_key:
        print("Error: FIRECRAWL_API_KEY environment variable not set.")
        print("Please set it: export FIRECRAWL_API_KEY='your_api_key'")
        return

    try:
        # Check for existing data to avoid re-scraping during development
        data_file = "rybno_data.json"
        
        if os.path.exists(data_file):
            print(f"Found existing {data_file}, loading raw data...")
            with open(data_file, 'r') as f:
                data = json.load(f)
                # Handle mismatch in structure if any
                if 'raw_scrape' in data:
                    result = data['raw_scrape']
                    print("Loaded raw_scrape from JSON.")
                else:
                    print("Old JSON format, will re-scrape.")
        
        if not result:
            client = FirecrawlClient(api_key=api_key)
            
            # Scrape the main page structure to get data
            # We want the main content in markdown to easily parse or feed to LLM later
            params = {
                'only_main_content': True
            }
            
            print(f"Starting scraping of {URL}...")
            result = client.scrape_url(URL, params=params)
            
        if result:
            if not os.path.exists(data_file):
                 print("Scraping successful!")
                
            # --- Parse Data ---
            structured_data = None
            markdown_content = ""
            
            # Extract markdown safely
            if isinstance(result, dict) and 'markdown' in result:
                markdown_content = result['markdown']
            elif hasattr(result, 'markdown'):
                markdown_content = result.markdown
            
            if markdown_content:
                print("Parsing markdown content...")
                parser = MarkdownParser(markdown_content)
                stats = parser.parse()
                structured_data = stats.model_dump()
                print("Parsing complete.")

            # --- Save Data ---
            output_file = "rybno_data.json"
            
            # Combine raw result and parsed data
            final_output = {
                "raw_scrape": result,
                "structured_data": structured_data
            }

            # Helper to convert object to dict (kept for robustness)
            def serialize(obj):
                if hasattr(obj, 'model_dump'):
                    return obj.model_dump()
                elif hasattr(obj, 'dict'):
                    return obj.dict()
                elif hasattr(obj, '__dict__'):
                    return obj.__dict__
                else:
                    return str(obj)

            with open(output_file, "w") as f:
                json.dump(final_output, f, indent=2, ensure_ascii=False, default=serialize)
            
            print(f"Data saved to {output_file}")
            
            if structured_data:
                print("\nExtracted Structured Data Snippet:")
                print(json.dumps(structured_data, indent=2, ensure_ascii=False)[:500] + "...")
            
    except Exception as e:
        print(f"An error occurred: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()
