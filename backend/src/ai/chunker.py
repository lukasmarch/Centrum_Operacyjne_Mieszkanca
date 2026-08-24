"""
SemanticChunker - splits documents into meaningful chunks for embedding
"""
import re
from typing import Optional

from src.utils.logger import setup_logger

logger = setup_logger("SemanticChunker")

# Optimal chunk size for text-embedding-3-small
MAX_CHUNK_SIZE = 500  # tokens (~2000 chars)
OVERLAP_SIZE = 50  # tokens overlap between chunks


class SemanticChunker:
    """Split documents into semantically meaningful chunks for RAG"""

    @staticmethod
    def chunk_article(
        title: str,
        content: Optional[str],
        summary: Optional[str],
        source_name: str = "",
        category: str = ""
    ) -> list[dict]:
        """
        Chunk an article into embeddable pieces.
        Returns list of {text, metadata} dicts.
        """
        chunks = []

        # Chunk 1: Title + summary (most important context)
        title_text = f"[{category}] {title}" if category else title
        if summary:
            chunk_text = f"{title_text}\n\n{summary}"
        else:
            chunk_text = title_text

        chunks.append({
            "text": chunk_text[:2000],
            "metadata": {
                "chunk_type": "title_summary",
                "source_name": source_name,
                "category": category
            }
        })

        # Chunk 2+: Content body (if exists and is long)
        if content and len(content) > 500:
            body_chunks = SemanticChunker._split_text(content, max_chars=1800, overlap_chars=200)
            for i, chunk in enumerate(body_chunks):
                chunks.append({
                    "text": f"{title_text}\n\n{chunk}",
                    "metadata": {
                        "chunk_type": "body",
                        "chunk_part": i + 1,
                        "source_name": source_name,
                        "category": category
                    }
                })

        return chunks

    @staticmethod
    def chunk_bip_document(
        title: str,
        content: Optional[str],
        doc_type: str = "uchwala"
    ) -> list[dict]:
        """Chunk a BIP document (uchwaly, przetargi, etc.)"""
        chunks = []

        header = f"[BIP - {doc_type}] {title}"

        if content:
            if len(content) <= 2000:
                chunks.append({
                    "text": f"{header}\n\n{content}",
                    "metadata": {"chunk_type": "full", "doc_type": doc_type}
                })
            else:
                parts = SemanticChunker._split_text(content, max_chars=1800, overlap_chars=200)
                for i, part in enumerate(parts):
                    chunks.append({
                        "text": f"{header}\n\n{part}",
                        "metadata": {"chunk_type": "part", "chunk_part": i + 1, "doc_type": doc_type}
                    })
        else:
            chunks.append({
                "text": header,
                "metadata": {"chunk_type": "title_only", "doc_type": doc_type}
            })

        return chunks

    @staticmethod
    def chunk_bip_static(
        title: str,
        content: Optional[str],
        section_name: str,
    ) -> list[dict]:
        """
        Chunk dokumentu ze stałych działów BIP (statut, podatki, programy).

        Nagłówek niesie dział, a nie samo `[BIP - dokument]` jak w chunkach
        aktualności: „Podatek rolny" bez kontekstu może być czymkolwiek,
        a „[BIP › Podatki i opłaty] Podatek rolny" mówi modelowi, w jakim
        rejestrze patrzy. Nagłówek powtarza się w KAŻDYM kawałku — inaczej
        drugi i dalsze fragmenty regulaminu trafiają do modelu bez informacji,
        czego dotyczą.
        """
        header = f"[BIP › {section_name}] {title}".strip()

        if not content:
            return [{
                "text": header,
                "metadata": {"chunk_type": "title_only", "section_name": section_name},
            }]

        parts = SemanticChunker._split_text(content, max_chars=1800, overlap_chars=200)
        return [
            {
                "text": f"{header}\n\n{part}",
                "metadata": {
                    "chunk_type": "bip_static",
                    "chunk_part": i + 1,
                    "chunk_total": len(parts),
                    "section_name": section_name,
                },
            }
            for i, part in enumerate(parts)
        ]

    @staticmethod
    def chunk_legal_act(
        title: str,
        content: Optional[str],
        act_number: Optional[str],
        act_group: str,
        adopted_at: Optional[str],
    ) -> list[dict]:
        """
        Chunk uchwały Rady albo zarządzenia Wójta.

        Nagłówek niesie NUMER i DATĘ, i to jest tu cała różnica wobec
        `chunk_bip_static`. Przy akcie prawnym podanie złego numeru nie jest
        drobną nieścisłością — mieszkaniec pójdzie z nim do urzędu. Numer musi
        więc stać w KAŻDYM kawałku, bo model cytuje to, co widzi obok tekstu,
        a nie to, co stało w kawałku pierwszym.

        Data w nagłówku odróżnia też akty o identycznych tytułach: „zmian
        w budżecie Gminy Rybno" to w 2026 r. kilkanaście osobnych zarządzeń.
        """
        stamp = f" z {adopted_at}" if adopted_at else ""
        number = f" NR {act_number}" if act_number else ""
        header = f"[{act_group}{number}{stamp}] {title}".strip()

        if not content:
            # Skan bez warstwy tekstowej — same metadane też są odpowiedzią
            # na pytanie „czy jest uchwała o…".
            return [{
                "text": header,
                "metadata": {
                    "chunk_type": "legal_act_title_only",
                    "act_number": act_number,
                    "act_group": act_group,
                },
            }]

        parts = SemanticChunker._split_text(content, max_chars=1800, overlap_chars=200)
        return [
            {
                "text": f"{header}\n\n{part}",
                "metadata": {
                    "chunk_type": "legal_act",
                    "chunk_part": i + 1,
                    "chunk_total": len(parts),
                    "act_number": act_number,
                    "act_group": act_group,
                },
            }
            for i, part in enumerate(parts)
        ]

    @staticmethod
    def chunk_event(
        title: str,
        description: Optional[str],
        location: Optional[str],
        date: str,
        category: str = ""
    ) -> list[dict]:
        """Chunk an event into a single embedding"""
        parts = [f"[Wydarzenie] {title}"]
        if date:
            parts.append(f"Data: {date}")
        if location:
            parts.append(f"Miejsce: {location}")
        if category:
            parts.append(f"Kategoria: {category}")
        if description:
            parts.append(description[:1000])

        return [{
            "text": "\n".join(parts),
            "metadata": {"chunk_type": "event", "category": category}
        }]

    @staticmethod
    def _split_text(text: str, max_chars: int = 1800, overlap_chars: int = 200) -> list[str]:
        """Tnie tekst, trzymając się granic akapitów i zdań.

        ⚠️ Preferencja granic to PREFERENCJA, nie gwarancja — i to była tu
        dziura. Akapit dłuższy niż `max_chars`, który trafiał na niepusty
        bufor, szedł do wyniku W CAŁOŚCI (gałąź dzielenia po zdaniach działa
        wyłącznie przy pustym buforze). Uchwała o Wieloletniej Prognozie
        Finansowej (XVIII/137/2025) to wielostronicowa tabela, z której PDF
        oddaje tekst bez akapitów — wyszedł z tego fragment 21 202 znaków przy
        celu 1800 i OpenAI odrzuciło go jako przekraczający 8192 tokeny.
        Osadzenie padało po cichu: jeden akt na 430 zostawał poza RAG.

        Drugi błąd w tej samej funkcji: `sent[:max_chars]` przy bardzo długim
        zdaniu OBCINAŁO resztę zamiast ją pociąć. Tekst znikał bez śladu.

        Dlatego na końcu idzie twardy podział: żaden fragment nie przekracza
        `max_chars`, a nic nie ginie.
        """
        if len(text) <= max_chars:
            return [text]

        chunks = []
        # Split by paragraphs first
        paragraphs = re.split(r'\n\s*\n', text)

        current_chunk = ""
        for para in paragraphs:
            para = para.strip()
            if not para:
                continue

            if len(current_chunk) + len(para) + 2 <= max_chars:
                current_chunk += ("\n\n" + para if current_chunk else para)
            else:
                if current_chunk:
                    chunks.append(current_chunk)
                    # Add overlap from end of previous chunk
                    overlap = current_chunk[-overlap_chars:] if len(current_chunk) > overlap_chars else ""
                    current_chunk = overlap + "\n\n" + para if overlap else para
                else:
                    # Single paragraph exceeds max_chars - split by sentences
                    sentences = re.split(r'(?<=[.!?])\s+', para)
                    for sent in sentences:
                        if len(current_chunk) + len(sent) + 1 <= max_chars:
                            current_chunk += (" " + sent if current_chunk else sent)
                        else:
                            if current_chunk:
                                chunks.append(current_chunk)
                            # Całe zdanie, nie `sent[:max_chars]` — obcięcie
                            # gubiło resztę bezpowrotnie. Nadmiar potnie
                            # `_enforce_limit`.
                            current_chunk = sent

        if current_chunk:
            chunks.append(current_chunk)

        return SemanticChunker._enforce_limit(chunks, max_chars, overlap_chars)

    @staticmethod
    def _enforce_limit(chunks: list[str], max_chars: int, overlap_chars: int) -> list[str]:
        """Twardy limit długości — ostatnia linia obrony przed odrzuceniem przez API.

        Dzieli wyłącznie to, czego podział semantyczny nie dał rady rozciąć
        (tabele z PDF, tekst bez spacji i akapitów). Zachodzenie fragmentów
        zostaje, żeby zdanie przecięte w połowie dało się odczytać w obu.
        """
        out: list[str] = []
        for chunk in chunks:
            if len(chunk) <= max_chars:
                out.append(chunk)
                continue
            step = max(max_chars - overlap_chars, max_chars // 2)
            for start in range(0, len(chunk), step):
                part = chunk[start:start + max_chars]
                if part:
                    out.append(part)
                if start + max_chars >= len(chunk):
                    break
        return out


# Singleton
chunker = SemanticChunker()
