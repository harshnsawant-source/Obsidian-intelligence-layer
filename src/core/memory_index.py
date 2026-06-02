import sys
import json
import hashlib
from pathlib import Path

import numpy as np

# Make the project root importable so `configs.paths` resolves regardless
# of which entrypoint loaded this module.
_ROOT = Path(__file__).resolve().parents[2]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from configs.paths import (
    KNOWLEDGE_VAULT,
    MEMORY_INDEX,
    EMBED_MODEL,
    EMBED_INPUT_CHAR_LIMIT
)
from core.embeddings import embed_text
from capability.core.search import search_directory


class MemoryIndex:

    # Semantic index over the knowledge vault ONLY. Incremental: each file
    # is embedded once and re-embedded only when its content hash changes.
    # Vectors persist locally as JSON. Falls back to keyword search when
    # embeddings are unavailable, so retrieval never hard-fails.

    def __init__(
        self,
        vault=KNOWLEDGE_VAULT,
        index_path=MEMORY_INDEX
    ):

        self.vault = Path(vault)

        self.index_path = Path(index_path)

        self.model = EMBED_MODEL

        self.entries = []

        self._load()

    def _load(self):

        if self.index_path.exists():

            try:

                data = json.loads(
                    self.index_path.read_text(encoding="utf-8")
                )

                self.entries = data.get("entries", [])

                self.model = data.get("model", self.model)

            except Exception:

                self.entries = []

    def _save(self):

        self.index_path.parent.mkdir(parents=True, exist_ok=True)

        dim = len(self.entries[0]["vector"]) if self.entries else 0

        payload = {
            "model": self.model,
            "dim": dim,
            "entries": self.entries
        }

        self.index_path.write_text(
            json.dumps(payload, indent=2),
            encoding="utf-8"
        )

    @staticmethod
    def _hash(text):

        return hashlib.sha1(
            text.encode("utf-8")
        ).hexdigest()

    def ensure_index(self):

        # Incrementally bring the index in sync with the vault.
        # Returns a small stats dict for observability/tests.

        existing = {e["file"]: e for e in self.entries}

        seen = set()

        new_entries = []

        added = 0

        updated = 0

        changed = False

        if not self.vault.exists():

            return {
                "total": 0,
                "added": 0,
                "updated": 0,
                "removed": 0
            }

        for file in sorted(self.vault.glob("*.md")):

            key = str(file)

            seen.add(key)

            try:

                content = file.read_text(
                    encoding="utf-8",
                    errors="ignore"
                )

            except Exception:

                continue

            file_hash = self._hash(content)

            previous = existing.get(key)

            if (
                previous
                and previous.get("hash") == file_hash
                and previous.get("vector")
            ):

                # Unchanged: reuse the stored vector (no re-embed).
                new_entries.append(previous)

                continue

            vector = embed_text(content[:EMBED_INPUT_CHAR_LIMIT])

            if vector is None:

                # Embeddings unavailable: keep any prior entry, otherwise
                # skip (search() will fall back to keyword matching).
                if previous:
                    new_entries.append(previous)

                continue

            new_entries.append({
                "file": key,
                "hash": file_hash,
                "mtime": file.stat().st_mtime,
                "snippet": content[:500],
                "vector": vector
            })

            changed = True

            if previous:
                updated += 1
            else:
                added += 1

        removed = len([k for k in existing if k not in seen])

        if removed:
            changed = True

        self.entries = new_entries

        if changed:
            self._save()

        return {
            "total": len(self.entries),
            "added": added,
            "updated": updated,
            "removed": removed
        }

    def search(self, query, k=5, min_score=0.25):

        self.ensure_index()

        query_vector = embed_text(query[:EMBED_INPUT_CHAR_LIMIT])

        if query_vector is None or not self.entries:

            return self._keyword_fallback(query, k)

        q = np.asarray(query_vector, dtype=float)

        q_norm = np.linalg.norm(q)

        if q_norm == 0:

            return self._keyword_fallback(query, k)

        results = []

        for entry in self.entries:

            v = np.asarray(entry["vector"], dtype=float)

            # Guard against a persisted index built with a different model
            # (different dimensionality).
            if v.shape != q.shape:
                continue

            v_norm = np.linalg.norm(v)

            if v_norm == 0:
                continue

            score = float(np.dot(q, v) / (q_norm * v_norm))

            if score >= min_score:

                results.append({
                    "file": entry["file"],
                    "score": round(score, 4),
                    "snippet": entry["snippet"]
                })

        results.sort(
            key=lambda x: x["score"],
            reverse=True
        )

        return results[:k]

    def _keyword_fallback(self, query, k):

        matches = search_directory(self.vault, query)

        results = []

        for match in matches[:k]:

            results.append({
                "file": match["file"],
                "score": None,
                "snippet": match.get("snippet", ""),
                "fallback": True
            })

        return results
