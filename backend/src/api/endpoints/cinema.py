from fastapi import APIRouter, HTTPException, Query
from src.scrapers.cinema import CinemaScraper, CinemaRepertoire

router = APIRouter()
scraper = CinemaScraper()

@router.get("/repertoire", response_model=CinemaRepertoire)
async def get_cinema_repertoire(location: str = Query(..., description="City name: 'Działdowo' or 'Lubawa'")):
    """
    Get cinema repertoire for a specific location.
    Scrapes data from Biletyna.pl in real-time (should be cached in production).
    """
    normalized_location = location.capitalize()
    if normalized_location not in ["Działdowo", "Lubawa", "Dzialdowo"]:
        # Fallback/default to Dzialdowo if unknown, or error?
        # Let's allow flexible input but mainly support these two
        pass
        
    try:
        # Use cache by default - only force_update during scheduled job (8 AM)
        data = scraper.fetch_repertoire(normalized_location, force_update=False)
        return data
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
