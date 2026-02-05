"""
Business Catalog Service for Gmina Rybno
Fetches business data from CEIDG and generates catalog + statistics
"""

import json
import os
from datetime import datetime
from typing import List, Dict, Any, Optional

from CEIDG_REGON.ceidg_client import (
    CEIDGClient, 
    extract_business_info, 
    generate_statistics,
    load_env
)

load_env()



class BusinessCatalog:
    """Service for managing Rybno business catalog"""
    
    def __init__(self, ceidg_token: str, output_dir: str = "data"):
        """
        Initialize catalog service.
        
        Args:
            ceidg_token: CEIDG API JWT token
            output_dir: Directory for output files
        """
        self.ceidg = CEIDGClient(api_token=ceidg_token)
        self.output_dir = output_dir
        os.makedirs(output_dir, exist_ok=True)
    
    def fetch_rybno_catalog(self) -> Dict[str, Any]:
        """
        Fetch complete business catalog for Gmina Rybno.
        
        Returns:
            Catalog dict with businesses and statistics
        """
        print("Fetching businesses from CEIDG for Gmina Rybno...")
        
        # Fetch all businesses
        raw_businesses = self.ceidg.fetch_all_businesses_in_gmina("Rybno")
        
        # Extract key info
        businesses = [extract_business_info(b) for b in raw_businesses]
        
        # Generate statistics
        stats = generate_statistics(businesses)
        
        # Add PKD section names
        stats["pkd_sections_names"] = {
            k: PKD_SECTIONS.get(k, "Nieznana sekcja") 
            for k in stats.get("by_pkd_section", {}).keys()
        }
        
        catalog = {
            "meta": {
                "gmina": "Rybno",
                "powiat": "działdowski",
                "wojewodztwo": "warmińsko-mazurskie",
                "source": "CEIDG",
                "last_updated": datetime.now().isoformat(),
                "description": "Katalog firm zarejestrowanych w Gminie Rybno"
            },
            "statistics": stats,
            "businesses": businesses
        }
        
        return catalog
    
    def save_catalog(self, catalog: Dict[str, Any], filename: str = "rybno_businesses.json") -> str:
        """
        Save catalog to JSON file.
        
        Args:
            catalog: Catalog dict
            filename: Output filename
            
        Returns:
            Path to saved file
        """
        filepath = os.path.join(self.output_dir, filename)
        
        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(catalog, f, indent=2, ensure_ascii=False)
        
        print(f"Catalog saved to: {filepath}")
        return filepath
    
    def generate_statistics_only(self, catalog: Dict[str, Any]) -> Dict[str, Any]:
        """
        Extract statistics for frontend display.
        
        Args:
            catalog: Full catalog dict
            
        Returns:
            Statistics-only dict for frontend
        """
        stats = catalog.get("statistics", {})
        
        # Convert PKD sections to readable format
        pkd_breakdown = []
        for code, count in sorted(
            stats.get("by_pkd_section", {}).items(), 
            key=lambda x: x[1], 
            reverse=True
        ):
            pkd_breakdown.append({
                "section": code,
                "name": PKD_SECTIONS.get(code, "Inna działalność"),
                "count": count,
                "percentage": round(count / stats.get("total", 1) * 100, 1)
            })
        
        # Convert miejscowości
        localities = []
        for name, count in sorted(
            stats.get("by_miejscowosc", {}).items(),
            key=lambda x: x[1],
            reverse=True
        ):
            localities.append({
                "name": name,
                "count": count
            })
        
        return {
            "total": stats.get("total", 0),
            "active": stats.get("active", 0),
            "suspended": stats.get("suspended", 0),
            "by_pkd": pkd_breakdown,
            "by_locality": localities,
            "last_updated": catalog.get("meta", {}).get("last_updated", "")
        }


def main():
    """Main function to generate business catalog"""
    
    # Get token from environment
    token = os.environ.get("CEIDG_API_TOKEN")
    
    if not token:
        print("=" * 60)
        print("CEIDG API Token Required!")
        print("=" * 60)
        print()
        print("1. Go to https://biznes.gov.pl and register")
        print("2. Get your API token")
        print("3. Set environment variable:")
        print("   export CEIDG_API_TOKEN='your-jwt-token'")
        print()
        print("Then run this script again.")
        return
    
    # Create catalog
    catalog_service = BusinessCatalog(ceidg_token=token)
    
    try:
        # Fetch and save
        catalog = catalog_service.fetch_rybno_catalog()
        catalog_service.save_catalog(catalog)
        
        # Also save statistics separately
        stats = catalog_service.generate_statistics_only(catalog)
        stats_path = os.path.join("data", "rybno_business_stats.json")
        with open(stats_path, "w", encoding="utf-8") as f:
            json.dump(stats, f, indent=2, ensure_ascii=False)
        print(f"Statistics saved to: {stats_path}")
        
        # Print summary
        print()
        print("=" * 60)
        print(f"Catalog Complete: {stats['total']} businesses found")
        print(f"Active: {stats['active']}, Suspended: {stats['suspended']}")
        print("=" * 60)
        
    except Exception as e:
        print(f"Error: {e}")
        raise


if __name__ == "__main__":
    main()
