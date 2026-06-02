import requests

from core.log import get_logger
from core.model_adapter import ModelAdapter
from configs.paths import LLM_MODEL


log = get_logger("llm_engine")


OLLAMA_URL = "http://localhost:11434/api/generate"

MODEL_NAME = LLM_MODEL


def query_llm(prompt, fmt=None, max_tokens=8000):

    # fmt="json" forces Ollama to emit valid JSON (and suppresses rambling /
    # thinking traces) — used for structured calls like plan decomposition.
    # max_tokens bounds generation so structured calls stay fast.

    payload = {

        "model": MODEL_NAME,

        "prompt": prompt,

        "stream": False,

        "options": {

            "temperature": 0.2,

            "num_predict": max_tokens

        }

    }

    if fmt:

        payload["format"] = fmt

    try:

        response = requests.post(

            OLLAMA_URL,

            json=payload,

            timeout=600

        )

        response.raise_for_status()

        data = response.json()

        log.debug("ollama response: %s", data)

        return ModelAdapter.normalize_response(data)

    except Exception as error:

        log.error("LLM call failed: %s", error)

        return f"LLM ERROR: {error}"