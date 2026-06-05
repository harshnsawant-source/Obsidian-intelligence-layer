# Provider definitions for the orchestration router.
#
# tier: 1 = highest quality. cost: $/1k tokens (0.0 = free).
# timeout: per-provider request timeout (seconds). Replaces the old hardcoded
#   600s. Cloud is fast, so 300s is generous; the local floor is capped low so a
#   stalled/looping local generation fails fast instead of blocking for minutes
#   (Phase A measured ~600s local timeouts dominating pipeline latency).
# An "openai_compat" provider activates automatically only if its api_key_env
# is set — so the upper tiers light up the moment you add a free key, with no
# code changes. Until then the router silently uses what's available.

PROVIDER_CONFIG = [

    # Tier 1 — free, remote, fast, most capable (Ollama cloud).
    {
        "name": "ollama-cloud-coder",
        "kind": "ollama",
        "model": "qwen3-coder:480b-cloud",
        "tier": 1,
        "local": False,
        "cost": 0.0,
        "timeout": 300,
        "enabled": True,
    },

    # Tier 4 — local floor: always available, fully private, no quota.
    # Capped at 120s: the local model is the failover floor, not where we wait
    # out long generations — a stall should surface fast and fail over.
    {
        "name": "ollama-local",
        "kind": "ollama",
        "model": "qwen3.5:4b",
        "tier": 4,
        "local": True,
        "cost": 0.0,
        "timeout": 120,
        "enabled": True,
    },
]

# Scope (for now): Ollama only — the free cloud coder + the local model.
# Claude (Pro) stays a manual, human-in-the-loop escalation tier; it is not a
# provider here (no API). The OpenAICompatProvider class remains available in
# core/providers/base.py if a free key-based provider is ever added later.
