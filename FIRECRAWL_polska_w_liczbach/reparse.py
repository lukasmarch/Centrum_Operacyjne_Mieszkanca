
import json
import sys
import os

# Add scraping dir to path
sys.path.append('scraping')

from scraping.parser import MarkdownParser
from scraping.models import GminaStats

def main():
    try:
        with open('rybno_data.json', 'r') as f:
            data = json.load(f)
            
        md = None
        if 'raw_scrape' in data and 'markdown' in data['raw_scrape']:
             md = data['raw_scrape']['markdown']
        elif 'markdown' in data: 
             md = data['markdown']
        elif 'raw_pages' in data and len(data['raw_pages']) > 0: # Handle rybno_full_data structure
             md = data['raw_pages'][0].get('markdown')
             
        if not md:
            print("No markdown found")
            return

        # Debug: Print lines around section header
        lines = md.split('\n')
        lines = md.split('\n')
        for i, line in enumerate(lines):
            if "Dział klasyfikacji budżetowej" in line:
                 print("FOUND TABLE HEADER AT", i)
                 for j in range(max(0, i-5), min(len(lines), i+15)):
                     print(f"{j}: {lines[j]}")
                 # Check next few lines for Ogolem
                 break
        
        parser = MarkdownParser(md)
        stats = parser.parse()
        
        # Verify budget details
        if stats.finance.budget_expenditure_details:
            print(f"SUCCESS: Extracted {len(stats.finance.budget_expenditure_details)} expenditure departments")
            print("Sample department:", stats.finance.budget_expenditure_details[0].model_dump())
        else:
            print("FAILURE: No expenditure details extracted")
            
        if stats.finance.budget_income_details:
             print(f"SUCCESS: Extracted {len(stats.finance.budget_income_details)} income departments")
        else:
             print("FAILURE: No income details extracted")
             
        # Merge stats into correct location
        if 'structured_data' in data:
             data['structured_data'] = stats.model_dump()
        else:
             data.update(stats.model_dump())
             
        # Save updated json
        with open('rybno_data.json', 'w') as f:
            json.dump(data, f, indent=2)
        print("Saved updated rybno_data.json")
        
        # Also update frontend/data.json
        with open('frontend/data.json', 'w') as f:
            json.dump(data, f, indent=2)
        print("Updated frontend/data.json")

    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()
