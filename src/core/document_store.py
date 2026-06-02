import re
from pathlib import Path

from core.memory_index import MemoryIndex
from core import db
from core.log import get_logger
from configs.paths import DOCUMENTS_DIR, DOC_INDEX


log = get_logger("documents")

CHUNK_CHARS = 1500
OVERLAP = 200


class DocumentStore:

    # Local document RAG. Ingest = read -> chunk -> write each chunk as a file
    # -> embed via the (local) MemoryIndex over a documents/ dir. Reuses all of
    # MemoryIndex's incremental embedding + cosine search + keyword fallback.
    # Document-level metadata lives in SQLite. Everything stays on-device.

    def __init__(self):
        self.dir = Path(DOCUMENTS_DIR)
        self.dir.mkdir(parents=True, exist_ok=True)
        self.index = MemoryIndex(vault=self.dir, index_path=DOC_INDEX)
        db.init_db()

    def _slug(self, name):
        return re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-") or "doc"

    def _chunk(self, text):
        text = (text or "").strip()
        chunks = []
        step = max(CHUNK_CHARS - OVERLAP, 1)
        i = 0
        while i < len(text):
            chunks.append(text[i:i + CHUNK_CHARS])
            i += step
        return chunks

    def ingest(self, path):
        source = Path(path)
        text = source.read_text(encoding="utf-8", errors="ignore")
        slug = self._slug(source.stem)

        # Replace any prior chunks for this document.
        for old in self.dir.glob(f"{slug}__chunk*.md"):
            old.unlink()

        chunks = self._chunk(text)
        for n, chunk in enumerate(chunks):
            (self.dir / f"{slug}__chunk{n:04d}.md").write_text(
                f"# source: {source.name} (chunk {n})\n\n{chunk}",
                encoding="utf-8",
            )

        db.register_document(str(source), source.name, len(chunks))
        stats = self.index.ensure_index()
        log.info("ingested %s -> %d chunks", source.name, len(chunks))
        return {"source": source.name, "chunks": len(chunks), "index": stats}

    def search(self, query, k=5):
        return self.index.search(query, k=k)

    def documents(self):
        return db.list_documents()
