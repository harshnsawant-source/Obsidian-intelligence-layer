# ReAct-style, model-agnostic tool loop. The model drives a small JSON text
# protocol over a plain completion endpoint; the policy decides what runs. The
# loop owns iteration + safety; tools only act. generate is injected, so the
# loop is fully testable offline. See TOOL_FRAMEWORK.md section 4.

from core.verifiers import extract_json   # shared lenient JSON extraction
from core.log import get_logger


log = get_logger("tools.loop")


class ToolRegistry:

    def __init__(self, tools=None):
        self.tools = {t.name: t for t in (tools or [])}

    def get(self, name):
        return self.tools.get(name)

    def allowed(self, policy):
        # Tools the policy permits — used to build the catalog the model sees.
        return [t for t in self.tools.values() if policy.allows(t)]


class LoopResult:

    def __init__(self, final, transcript, steps, completed):
        self.final = final
        self.transcript = transcript   # list of {action, observation}
        self.steps = steps
        self.completed = completed      # True if the model emitted a final

    def __repr__(self):
        return (
            f"LoopResult(completed={self.completed}, steps={self.steps}, "
            f"final={self.final!r:.60})"
        )


PROTOCOL = """You can use tools to complete the task. Available tools:
{catalog}

To use a tool, reply with ONLY this JSON and nothing else:
{{"tool": "<name>", "args": {{...}}}}

When you have the final answer, reply with ONLY:
{{"final": "<your answer>"}}
"""


def _prompt(task, catalog, transcript):
    history = ""
    for turn in transcript:
        history += (
            f'\nACTION: {turn["action"]}\nOBSERVATION: {turn["observation"]}\n'
        )
    return f"""{PROTOCOL.format(catalog=catalog)}
Task:
{task}
{history}
Your next step (one JSON object only):"""


def run_tool_loop(generate, task, registry, policy, max_steps=6):

    # generate(prompt) -> str. Never raises: tool errors and bad model output
    # become observations; exhaustion returns a best-effort final.

    allowed = registry.allowed(policy)

    catalog = "\n".join(t.spec() for t in allowed) or "(no tools available)"

    transcript = []

    last_text = ""

    for step in range(1, max_steps + 1):

        raw = generate(_prompt(task, catalog, transcript))

        last_text = raw or ""

        data = extract_json(raw)

        if isinstance(data, dict) and "final" in data:
            log.debug("tool loop completed on step %d", step)
            return LoopResult(
                str(data["final"]), transcript, step, completed=True
            )

        if isinstance(data, dict) and "tool" in data:
            name = data.get("tool")
            args = data.get("args") or {}
            observation = _invoke(registry, policy, name, args)
            transcript.append({
                "action": f'{name}({args})',
                "observation": observation,
            })
            continue

        # Unparseable / off-protocol: nudge and keep going.
        transcript.append({
            "action": "(no valid tool call)",
            "observation": (
                'Respond with ONLY a JSON object: {"tool": ...} to act or '
                '{"final": ...} to finish.'
            ),
        })

    log.warning("tool loop hit max_steps (%d) without a final", max_steps)

    # Best effort: surface the model's last text as the answer.
    return LoopResult(last_text, transcript, max_steps, completed=False)


def _invoke(registry, policy, name, args):

    tool = registry.get(name)

    if tool is None:
        return f"unknown tool: {name}"

    allowed, reason = policy.decide(tool)

    if not allowed:
        log.debug("tool %s denied: %s", name, reason)
        return f"DENIED: {reason}"

    try:
        result = tool.run(args if isinstance(args, dict) else {})
    except Exception as error:
        log.warning("tool %s raised: %s", name, error)
        return f"tool error: {error}"

    return result.observation
