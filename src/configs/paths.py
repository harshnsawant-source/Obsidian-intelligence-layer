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