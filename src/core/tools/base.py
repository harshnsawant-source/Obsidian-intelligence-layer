# Tool interface + result + risk tiers. Pure: no LLM, no policy, no I/O here.
# Risk lives on the tool; the ALLOW/DENY decision lives in the policy. See
# TOOL_FRAMEWORK.md sections 2-3.


class Risk:
    # Assign by worst-case side effect (see TOOL_FRAMEWORK.md section 2.3).
    SAFE = "safe"           # read-only, no egress, no mutation
    MODERATE = "moderate"   # bounded / sandboxed mutation
    DANGEROUS = "dangerous" # unbounded side effects or egress


class ToolResult:

    # `output` (success) or `error` (failure) becomes the observation fed back
    # to the model — keep it concrete and actionable.

    def __init__(self, ok, output="", error=""):
        self.ok = bool(ok)
        self.output = output or ""
        self.error = error or ""

    @property
    def observation(self):
        return self.output if self.ok else (self.error or "tool failed")

    def __repr__(self):
        return f"ToolResult(ok={self.ok})"


class Tool:

    # A capability the model can invoke. Subclasses set the class attributes and
    # implement run(). run() must NOT raise for ordinary failure — return a
    # ToolResult(ok=False, error=...) instead so the model gets a useful
    # observation. The loop wraps run() defensively regardless.

    name = "tool"
    description = ""
    parameters = {}          # arg name -> human description (prompt catalog)
    risk = Risk.MODERATE
    network = False          # does it egress off-device? (privacy gate)

    def run(self, args):
        raise NotImplementedError

    def spec(self):
        # One catalog entry for the prompt.
        params = ", ".join(
            f"{k} ({v})" for k, v in self.parameters.items()
        ) or "none"
        return f'- {self.name}: {self.description} | args: {params}'
