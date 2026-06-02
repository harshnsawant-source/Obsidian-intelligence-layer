import time

import requests

from core.model_adapter import ModelAdapter
from core.log import get_logger


log = get_logger("providers")

OLLAMA_URL = "http://localhost:11434/api/generate"


class Provider:

    # A provider must raise on failure so the router can fail over. The router
    # is responsible for never raising to callers (it has a canned floor).

    kind = "base"

    def __init__(self, name, model, tier=4, local=False, cost=0.0):
        self.name = name
        self.model = model
        self.tier = tier
        self.local = local
        self.cost = cost

    def generate(self, prompt, fmt=None, max_tokens=8000):
        raise NotImplementedError


class OllamaProvider(Provider):

    kind = "ollama"

    def generate(self, prompt, fmt=None, max_tokens=8000):

        payload = {
            "model": self.model,
            "prompt": prompt,
            "stream": False,
            "options": {"temperature": 0.2, "num_predict": max_tokens},
        }

        if fmt:
            payload["format"] = fmt

        started = time.time()

        response = requests.post(OLLAMA_URL, json=payload, timeout=600)

        response.raise_for_status()

        data = response.json()

        if data.get("error"):
            raise RuntimeError(f"{self.name}: {data['error']}")

        text = ModelAdapter.normalize_response(data)

        log.debug("%s ok in %.1fs", self.name, time.time() - started)

        return text


class OpenAICompatProvider(Provider):

    # Works for OpenRouter / Groq / Together and any OpenAI-compatible endpoint.
    # Dormant until an API key is supplied (the registry skips it otherwise).

    kind = "openai_compat"

    def __init__(self, name, model, base_url, api_key, tier=2, cost=0.0):
        super().__init__(name, model, tier=tier, local=False, cost=cost)
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key

    def generate(self, prompt, fmt=None, max_tokens=8000):

        body = {
            "model": self.model,
            "messages": [{"role": "user", "content": prompt}],
            "max_tokens": max_tokens,
            "temperature": 0.2,
        }

        if fmt == "json":
            body["response_format"] = {"type": "json_object"}

        response = requests.post(
            f"{self.base_url}/chat/completions",
            json=body,
            headers={"Authorization": f"Bearer {self.api_key}"},
            timeout=300,
        )

        response.raise_for_status()

        return response.json()["choices"][0]["message"]["content"]
