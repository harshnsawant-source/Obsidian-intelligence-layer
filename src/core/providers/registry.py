import os

from core.providers.base import OllamaProvider, OpenAICompatProvider
from core.circuit_breaker import CircuitBreaker
from core.log import get_logger
from configs.providers import PROVIDER_CONFIG


log = get_logger("registry")


class ManagedProvider:

    # Pairs a Provider with its circuit breaker and exposes the routing
    # metadata the router sorts on.

    def __init__(self, provider):
        self.provider = provider
        self.breaker = CircuitBreaker()

    @property
    def name(self):
        return self.provider.name

    @property
    def tier(self):
        return self.provider.tier

    @property
    def local(self):
        return self.provider.local

    @property
    def cost(self):
        return self.provider.cost


def build_registry():

    managed = []

    for cfg in PROVIDER_CONFIG:

        if not cfg.get("enabled", True):
            continue

        kind = cfg["kind"]

        if kind == "ollama":
            provider = OllamaProvider(
                cfg["name"], cfg["model"],
                tier=cfg["tier"], local=cfg["local"], cost=cfg.get("cost", 0.0),
            )

        elif kind == "openai_compat":
            key = os.environ.get(cfg["api_key_env"], "")
            if not key:
                # Dormant until a key is supplied — never an error.
                continue
            provider = OpenAICompatProvider(
                cfg["name"], cfg["model"], cfg["base_url"], key,
                tier=cfg["tier"], cost=cfg.get("cost", 0.0),
            )

        else:
            log.warning("unknown provider kind: %s", kind)
            continue

        managed.append(ManagedProvider(provider))

    log.debug("registry: %s", [m.name for m in managed])

    return managed
