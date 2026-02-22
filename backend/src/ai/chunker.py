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
        """Split text into chunks, preferring paragraph/sentence boundaries"""
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
                            current_chunk = sent[:max_chars]

        if current_chunk:
            chunks.append(current_chunk)

        return chunks


# Singleton
chunker = SemanticChunker()
