FROM python:3.11-slim
WORKDIR /app

# ffmpeg/ffprobe: transkrypcja sesji Rady (services/council_transcript.py) —
# konwersja audio do 16 kHz mono i cięcie na chunki mieszczące się w Whisperze.
# yt-dlp woła oba binaria po nazwie, więc muszą być w PATH obrazu.
RUN apt-get update && apt-get install -y \
    gcc libpq-dev libxml2-dev libxslt1-dev ffmpeg \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY src/ src/
COPY data/ data/
COPY scripts/ scripts/
COPY assets/ assets/

RUN mkdir -p uploads/reports logs

EXPOSE 8000
CMD ["uvicorn", "src.api.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "1"]
