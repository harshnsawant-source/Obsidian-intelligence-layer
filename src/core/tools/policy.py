# The single place every allow/deny decision is made, so the rule set is
# auditable in one function. Generalizes the sandbox's default-deny posture to
# all side-effecting tools. See TOOL_FRAMEWORK.md section 3.

from core.tools.base import Risk


class Policy:

    def __init__(self, allow=None, sensitive=False):
        # allow: names of DANGEROUS tools explicitly granted.
        # sensitive: a privacy-pinned run — forbids ALL network tools.
        self.allow = set(allow or [])
        self.sensitive = sensitive

    def decide(self, tool):

        # Returns (allowed: bool, reason: str). Rules in priority order:

        # 1. Privacy egress block — outranks everything, including the
        #    allow-list. The same boundary that pins sensitive LLM calls to
        #    local models also forbids tools that leave the device.
        if tool.network and self.sensitive:
            return False, (
                "privacy: network tools are disabled on sensitive runs"
            )

        # 2. Default-deny for DANGEROUS — runs only if granted by name.
        if tool.risk == Risk.DANGEROUS and tool.name not in self.allow:
            return False, (
                f"dangerous tool '{tool.name}' is not in the allow-list "
                f"(default-deny)"
            )

        # 3. Everything else (SAFE / MODERATE) is allowed; its safety comes
        #    from being built bounded, not from per-call permission.
        return True, "ok"

    def allows(self, tool):
        return self.decide(tool)[0]
