# Wersja interpretera przypięta (jak prod 13.10.2026: 3.11.16) — ruchomy tag 3.11 zmieniałby się przy każdej przebudowie
FROM python:3.11.16-slim
WORKDIR /app

# ffmpeg/ffprobe: transkrypcja sesji Rady (services/council_transcript.py) —
# konwersja audio do 16 kHz mono i cięcie na chunki mieszczące się w Whisperze.
# yt-dlp woła oba binaria po nazwie, więc muszą być w PATH obrazu.
RUN apt-get update && apt-get install -y \
    gcc libpq-dev libxml2-dev libxslt1-dev ffmpeg \
    && rm -rf /var/lib/apt/lists/*

# constraints.txt = pip freeze produkcji (203 pakiety). Przebudowa daje TE SAME wersje;
# odświeżanie świadome: scripts/refresh_constraints.sh
COPY requirements.txt constraints.txt ./
RUN pip install --no-cache-dir -r requirements.txt -c constraints.txt

COPY src/ src/
COPY data/ data/
COPY scripts/ scripts/
COPY assets/ assets/

RUN mkdir -p uploads/reports logs private_uploads/solectwa

EXPOSE 8000
CMD ["uvicorn", "src.api.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "1"]
