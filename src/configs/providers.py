# Provider definitions for the orchestration router.
#
# tier: 1 = highest quality. cost: $/1k tokens (0.0 = free).
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
        "enabled": True,
    },

    # Tier 4 — local floor: always available, fully private, no quota.
    {
        "name": "ollama-local",
        "kind": "ollama",
        "model": "qwen3.5:4b",
        "tier": 4,
        "local": True,
        "cost": 0.0,
        "enabled": True,
    },

    # ---- Optional free-cloud tiers: dormant until you add a (free) key. ----
    {
        "name": "groq",
        "kind": "openai_compat",
        "model": "llama-3.3-70b-versatile",
        "base_url": "https://api.groq.com/openai/v1",
        "api_key_env": "GROQ_API_KEY",
        "tier": 2,
        "local": False,
        "cost": 0.0,
        "enabled": True,
    },
    {
        "name": "openrouter",
        "kind": "openai_compat",
        "model": "deepseek/deepseek-chat",
        "base_url": "https://openrouter.ai/api/v1",
        "api_key_env": "OPENROUTER_API_KEY",
        "tier": 3,
        "local": False,
        "cost": 0.0,
        "enabled": True,
    },
]
