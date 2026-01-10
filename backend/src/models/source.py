from pydantic import BaseModel
from typing import Optional, Dict

class SourceConfig(BaseModel):
    name: str
    type: str
    url: str
    scraping_config: Optional[Dict] = None
