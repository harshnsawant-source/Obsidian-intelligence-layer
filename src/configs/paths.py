from pathlib import Path


# src/configs/paths.py -> parents[2] is the project root.
BASE_DIR = Path(__file__).resolve().parents[2]

DOCS = BASE_DIR / "docs"

MEMORY = BASE_DIR / "memory"

LOGS = BASE_DIR / "logs"

RUNTIME = BASE_DIR / "runtime"

SRC = BASE_DIR / "src"

CONFIGS = SRC / "configs"


KNOWLEDGE_VAULT = SRC / "knowledge" / "vault"


# Generation models are defined in configs/providers.py and selected at
# runtime by the orchestration router (core/router.py). Embeddings stay local.
EMBED_MODEL = "nomic-embed-text"

EMBED_FALLBACK_MODEL = "qwen3.5:4b"

MEMORY_INDEX = SRC / "state" / "index" / "vault_index.json"

# Char budget per embedding call. nomic-embed-text caps at 2048 tokens;
# token-dense notes exceed that well before their full length, so we
# truncate the head of each note (and query) to a safe size.
EMBED_INPUT_CHAR_LIMIT = 4000


# K-B: the user's real Obsidian vault. This project lives at <vault>/projects/
# obsidian-intelligence-layer, so the vault root is two levels above BASE_DIR.
# Notes are indexed READ-ONLY into state/ (never written back into the vault).
# Retrieval over these private notes is LOCAL-ONLY.
OBSIDIAN_VAULT = BASE_DIR.parent.parent
VAULT_NOTES_INDEX = SRC / "state" / "index" / "vault_notes_index.json"

# Directories never ingested (the OIL project itself, Obsidian config, binaries,
# tooling/vendor, agent runtime). Matched against any path segment.
VAULT_EXCLUDE_DIRS = {
    "projects", ".obsidian", ".git", ".claude", "node_modules",
    "assets", "Templates", "helpers", "openclaw",
}
# Filename substrings that mark generated/exported artifacts (not real notes).
VAULT_EXCLUDE_NAME_SUBSTRINGS = ("generated",)


# Document RAG + structured stores (Phase 2). All local (privacy).
DOCUMENTS_DIR = SRC / "state" / "documents"
DOC_INDEX = SRC / "state" / "index" / "doc_index.json"
DB_PATH = SRC / "state" / "db" / "oil.sqlite"
ESCALATIONS = RUNTIME / "escalations.md"


HELPERS = BASE_DIR.parent.parent / "helpers"


RETRIEVAL_PATHS = [

    DOCS,

    MEMORY,

    LOGS
]