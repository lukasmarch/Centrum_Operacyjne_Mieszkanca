#!/usr/bin/env python3
"""
Crawl all subpages of polskawliczbach.pl for Gmina Rybno.
This collects data from all sections: Ludność, Ekonomia, Nieruchomości, etc.
"""
import os
import sys
import json
from firecrawl_client import FirecrawlClient
from parser import MarkdownParser

# Force unbuffered output
sys.stdout.reconfigure(line_buffering=True)

# Target URL - the main page of Gmina Rybno
URL = "https://www.polskawliczbach.pl/gmina_Rybno_warminsko_mazurskie"

def serialize(obj):
    """Helper to convert objects to dict for JSON serialization."""
    if hasattr(obj, 'model_dump'):
        return obj.model_dump()
    elif hasattr(obj, 'dict'):
        return obj.dict()
    elif hasattr(obj, '__dict__'):
        return obj.__dict__
    else:
        return str(obj)

def main():
    # Check for API key
    api_key = os.getenv("FIRECRAWL_API_KEY")
    if not api_key:
        print("Error: FIRECRAWL_API_KEY environment variable not set.", flush=True)
        print("Please set it: export FIRECRAWL_API_KEY='your_api_key'", flush=True)
        return

    try:
        print(f"Initializing client...", flush=True)
        client = FirecrawlClient(api_key=api_key)
        
        print(f"Starting full site crawl of {URL}...", flush=True)
        
        # Crawl with a reasonable limit - the site has ~10-15 relevant sections
        # We request markdown format for easier parsing
        try:
            from firecrawl.types import ScrapeOptions
            scrape_opts = ScrapeOptions(formats=['markdown'], only_main_content=True)
        except ImportError:
            # Fallback if ScrapeOptions not available
            scrape_opts = None
        
        crawl_result = client.crawl_url(
            url=URL,
            limit=25,  # Should cover all sections
            scrape_options=scrape_opts,
            poll_interval=30
        )
        
        if crawl_result:
            print(f"Crawl completed!")
            
            # Extract pages from crawl result
            pages = []
            if hasattr(crawl_result, 'data'):
                pages = crawl_result.data
            elif isinstance(crawl_result, dict) and 'data' in crawl_result:
                pages = crawl_result['data']
            elif isinstance(crawl_result, list):
                pages = crawl_result
            
            print(f"Crawled {len(pages)} pages.")
            
            # --- Parse All Pages ---
            all_sections_text = ""
            page_info = []
            
            for i, page in enumerate(pages):
                # Extract URL and markdown
                page_url = ""
                markdown = ""
                
                if hasattr(page, 'metadata') and hasattr(page.metadata, 'url'):
                    page_url = page.metadata.url
                elif isinstance(page, dict):
                    page_url = page.get('metadata', {}).get('url', f'page_{i}')
                
                if hasattr(page, 'markdown'):
                    markdown = page.markdown
                elif isinstance(page, dict):
                    markdown = page.get('markdown', '')
                
                page_info.append({
                    'url': page_url,
                    'markdown_length': len(markdown)
                })
                
                # Concatenate all markdown for unified parsing
                all_sections_text += f"\n\n--- PAGE: {page_url} ---\n\n{markdown}"
            
            print("\nPages crawled:")
            for info in page_info:
                print(f"  - {info['url']} ({info['markdown_length']} chars)")
            
            # Parse all combined text
            print("\nParsing combined data...")
            parser = MarkdownParser(all_sections_text)
            stats = parser.parse()
            structured_data = stats.model_dump()
            
            # --- Save Data ---
            output_file = "rybno_full_data.json"
            
            final_output = {
                "crawl_summary": {
                    "pages_crawled": len(pages),
                    "pages": page_info
                },
                "structured_data": structured_data,
                "raw_pages": [serialize(p) for p in pages]
            }
            
            with open(output_file, "w") as f:
                json.dump(final_output, f, indent=2, ensure_ascii=False, default=serialize)
            
            print(f"\nData saved to {output_file}")
            
            # Print summary of extracted data
            print("\n" + "="*50)
            print("EXTRACTED DATA SUMMARY")
            print("="*50)
            print(json.dumps(structured_data, indent=2, ensure_ascii=False))
            
    except Exception as e:
        print(f"An error occurred: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()
