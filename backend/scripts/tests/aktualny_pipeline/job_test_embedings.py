import asyncio

import sys
from pathlib import Path

backend_path = Path(__file__).resolve().parent.parent.parent.parent
sys.path.insert(0, str(backend_path))

from src.scheduler.embedding_job import run_embedding_job_async

asyncio.run(run_embedding_job_async())