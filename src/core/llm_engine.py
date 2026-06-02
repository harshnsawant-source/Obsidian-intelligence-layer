from core.router import ProviderRouter


# Single shared router: complexity-aware provider selection, circuit-breaker
# failover, local floor. Callers keep using query_llm() unchanged.
_router = ProviderRouter()


def query_llm(prompt, fmt=None, max_tokens=8000, sensitive=False):

    # fmt="json" forces structured output; sensitive=True keeps the request on
    # local models only (privacy). Always returns a string (never raises).

    return _router.generate(
        prompt,
        fmt=fmt,
        max_tokens=max_tokens,
        sensitive=sensitive,
    )
