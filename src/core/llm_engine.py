import requests

from core.log import get_logger
from core.model_adapter import ModelAdapter


log = get_logger("llm_engine")


OLLAMA_URL = "http://localhost:11434/api/generate"

MODEL_NAME = "qwen3.5:4b"


def query_llm(prompt):

    payload = {

        "model": MODEL_NAME,

        "prompt": prompt,

        "stream": False,

        "options": {

            "temperature": 0.2,

            "num_predict": 8000

        }

    }

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