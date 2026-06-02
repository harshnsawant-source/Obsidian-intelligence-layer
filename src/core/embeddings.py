import sys
from pathlib import Path
from collections import OrderedDict

import requests

# Make the project root importable so `configs.paths` resolves regardless
# of which entrypoint loaded this module.
_ROOT = Path(__file__).resolve().parents[2]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from configs.paths import EMBED_MODEL, EMBED_FALLBACK_MODEL
from core.log import get_logger


log = get_logger("embeddings")


OLLAMA_EMBED_URL = "http://localhost:11434/api/embed"

OLLAMA_EMBED_URL_LEGACY = "http://localhost:11434/api/embeddings"

TIMEOUT = 120

# Models that have permanently failed this session (missing, or no embedding
# support). Cached so we never re-pay the cost: a chat model like qwen3.5:4b
# takes ~8s to load just to return "does not support embeddings". After one
# failure we return None instantly and let callers fall back to keyword search.
_unavailable_models = set()

_PERMANENT_ERRORS = (
    "not found",
    "does not support",
    "not support",
    "try pulling"
)

# LRU cache of successful embeddings keyed by input text. Identical inputs
# (e.g. the same task embedded by several agents in one A2A cascade, or a
# repeated query) skip the ~2s embedding round-trip. Failures are never
# cached, so the model is retried if it recovers.
_CACHE_MAX = 512

_embed_cache = OrderedDict()


def _mark_unavailable(model):

    if model not in _unavailable_models:

        _unavailable_models.add(model)

        log.warning(
            "embedding model unavailable this session: %s", model
        )


def _try_endpoint(url, payload):

    # Returns (vector_or_None, permanent_failure_bool).

    try:

        response = requests.post(url, json=payload, timeout=TIMEOUT)

    except Exception:

        return None, False

    try:

        data = response.json()

    except Exception:

        return None, False

    if response.status_code == 200:

        embeddings = data.get("embeddings")

        if embeddings:
            return embeddings[0], False

        embedding = data.get("embedding")

        if embedding:
            return embedding, False

    error = str(data.get("error", "")).lower()

    # Only 404 (model missing) / 501 (no embedding support) mean the MODEL
    # is unusable. A 400 is input-specific (e.g. input too long) and must
    # NOT blacklist the model, or one oversized note would disable semantic
    # search for the whole session.
    permanent = (
        response.status_code in (404, 501)
        or any(token in error for token in _PERMANENT_ERRORS)
    )

    return None, permanent


def _embed_one(text, model):

    if not model or model in _unavailable_models:
        return None

    vector, permanent = _try_endpoint(
        OLLAMA_EMBED_URL,
        {"model": model, "input": text}
    )

    if vector is not None:
        return vector

    if permanent:
        _mark_unavailable(model)
        return None

    vector, permanent = _try_endpoint(
        OLLAMA_EMBED_URL_LEGACY,
        {"model": model, "prompt": text}
    )

    if vector is not None:
        return vector

    if permanent:
        _mark_unavailable(model)

    return None


def embed_text(text):

    # Returns a list[float] embedding, or None if embeddings are
    # unavailable (so callers can fall back to keyword search).

    if not text or not str(text).strip():
        return None

    cached = _embed_cache.get(text)

    if cached is not None:
        _embed_cache.move_to_end(text)
        return cached

    vector = _embed_one(text, EMBED_MODEL)

    if vector is None:
        vector = _embed_one(text, EMBED_FALLBACK_MODEL)

    if vector is not None:

        _embed_cache[text] = vector
        _embed_cache.move_to_end(text)

        if len(_embed_cache) > _CACHE_MAX:
            _embed_cache.popitem(last=False)

    return vector


def embed_batch(texts):

    return [embed_text(text) for text in texts]
