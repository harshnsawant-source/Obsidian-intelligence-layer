# K-B: read-only retrieval over the user's real Obsidian vault.
#
# Reuses the local MemoryIndex (incremental embed + cosine + keyword fallback)
# with recursive discovery + excludes. The vault notes are NEVER modified — the
# only artifact written is the index under state/. Retrieval is LOCAL-ONLY:
# embeddings are the local nomic model and search makes no chat-LLM call, so
# private notes never leave the device. Source path + folder are preserved on
# every result to support folder-scoped retrieval.
#
# This is a separate namespace from the agent-distillation vault and the
# document-RAG store. It does not touch routing, planner, or orchestration.

from pathlib import Path

from configs.paths import (
    OBSIDIAN_VAULT,
    VAULT_NOTES_INDEX,
    VAULT_EXCLUDE_DIRS,
    VAULT_EXCLUDE_NAME_SUBSTRINGS,
)
from core.memory_index import MemoryIndex
from core.log import get_logger


log = get_logger("vault-store")


class VaultStore:

    def __init__(self, vault=OBSIDIAN_VAULT, index_path=VAULT_NOTES_INDEX):

        self.vault = Path(vault)

        self.index = MemoryIndex(
            vault=self.vault,
            index_path=index_path,
            recursive=True,
            exclude_dirs=VAULT_EXCLUDE_DIRS,
            exclude_name_substrings=VAULT_EXCLUDE_NAME_SUBSTRINGS,
        )

    def reindex(self):

        # Incremental: only changed/new notes are re-embedded. Returns stats.
        stats = self.index.ensure_index()

        log.info(
            "vault index: %d notes (added %d, updated %d, removed %d)",
            stats.get("total", 0), stats.get("added", 0),
            stats.get("updated", 0), stats.get("removed", 0),
        )

        return stats

    def _folder(self, path):

        # Top-level folder under the vault, or "(root)" for a root note.
        try:
            parts = Path(path).resolve().relative_to(self.vault.resolve()).parts
        except ValueError:
            return "(root)"

        return parts[0] if len(parts) > 1 else "(root)"

    def search(self, query, k=5, folder=None):

        # Retrieval only (local embeddings + cosine, keyword fallback). No
        # chat-LLM call -> nothing leaves the device. `folder` (e.g. "daily-ops")
        # restricts results to that top-level folder, using stored path metadata.
        # ensure_index() runs inside search(), so the index self-syncs on use.

        # Pull a wider candidate set when filtering by folder (small corpus).
        raw = self.index.search(query, k=(200 if folder else k))

        results = []
        for r in raw:
            fld = self._folder(r["file"])
            if folder and fld != folder:
                continue
            results.append({
                "source": r["file"],
                "folder": fld,
                "score": r.get("score"),
                "snippet": r.get("snippet", ""),
            })
            if len(results) >= k:
                break

        return results

    def folders(self):

        # Distinct top-level folders currently represented in the index.
        self.index.ensure_index()
        return sorted({self._folder(e["file"]) for e in self.index.entries})
