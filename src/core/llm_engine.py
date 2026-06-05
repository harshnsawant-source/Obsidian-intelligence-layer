from core.router import ProviderRouter


# Single shared router: complexity-aware provider selection, circuit-breaker
# failover, local floor. Callers keep using query_llm() unchanged.
_router = ProviderRouter()


def query_llm(prompt, fmt=None, max_tokens=8000, sensitive=False,
              prefer_cloud=False, expects_code=False):

    # fmt="json" forces structured output; sensitive=True keeps the request on
    # local models only (privacy); prefer_cloud=True routes a low-complexity
    # call cloud-first for quality (local stays as the failover floor, and
    # sensitive still wins); expects_code=True marks a code-generation call so
    # the router cloud-pins it (non-sensitive) — local is unreliable for code.
    # Always returns a string (never raises).

    return _router.generate(
        prompt,
        fmt=fmt,
        max_tokens=max_tokens,
        sensitive=sensitive,
        prefer_cloud=prefer_cloud,
        expects_code=expects_code,
    )
