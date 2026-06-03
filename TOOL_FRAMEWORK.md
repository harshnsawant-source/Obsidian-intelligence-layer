# Tool Execution Framework — Design Blueprint

> Reusable blueprint. Describes how an agent system lets a model **take actions**
> (run code, read/write files, fetch the web) safely. The abstractions (`Tool`,
> `Policy`, `run_tool_loop`) are decoupled from this codebase so they lift into
> other systems unchanged. This is the direct generalization of the sandbox's
> default-deny posture from `VERIFICATION.md` §4 into a uniform permission model
> over *all* side-effecting actions.

## 1. What this solves

Verification made the model's *output* trustworthy. Tools make the model
*capable of acting* — but every action is a side effect, and model-chosen
actions are an attack/footgun surface. The framework's job is to let a model
call tools **autonomously** while a single, auditable policy decides what is
allowed. Two failure modes it must prevent:

1. **Unbounded side effects** — arbitrary file writes, shell, network egress
   chosen by a model that can be wrong or prompt-injected.
2. **Privacy leakage** — a tool (web fetch, shell `curl`) exfiltrating private
   data during a `sensitive` run. The privacy boundary that pins sensitive LLM
   calls to local models must *also* forbid network tools.

## 2. Core abstractions

Three pieces, same minimalist spirit as the verification layer.

### 2.1 `Tool`
A capability the model can invoke. Declares its risk so the policy can reason
about it without knowing the specific tool.

```
Tool:
  name        str     # stable identifier the model emits
  description str     # what it does (goes into the prompt catalog)
  parameters  dict    # arg name -> human description (prompt catalog)
  risk        Risk    # SAFE | MODERATE | DANGEROUS
  network     bool    # does it egress off-device? (privacy gate)
  run(args: dict) -> ToolResult
```

`run` must **never raise for ordinary failure** — it returns
`ToolResult(ok=False, error=...)`. The loop wraps it defensively anyway, but
tools own their error reporting so the model gets actionable observations.

### 2.2 `ToolResult`
```
ToolResult(ok: bool, output: str, error: str)
```
`output` (on success) or `error` (on failure) becomes the **observation** fed
back to the model. Keep it concrete: a stack trace, the file contents, the HTTP
body — not "it worked."

### 2.3 Risk tiers
The single axis the policy reasons over. Assign by *worst-case side effect*:

| Risk | Meaning | Examples |
|---|---|---|
| `SAFE` | read-only, no egress, no mutation | read_file (path-jailed), list_dir |
| `MODERATE` | bounded/sandboxed mutation | python (sandbox), write_file (jailed to a work root) |
| `DANGEROUS` | unbounded side effects or egress | shell, web_fetch, write to arbitrary path |

`network=True` is **orthogonal** to risk — a tool can be low-risk locally but
still egress. The policy treats egress separately (see §3) because privacy is a
different concern from blast radius.

## 3. The permission policy (the centerpiece)

One function decides everything, so the rule set is auditable in one place:

```
Policy(allow: set[str], sensitive: bool)

decide(tool) -> (allowed: bool, reason: str):
    if tool.network and self.sensitive:
        return False, "privacy: network tools disabled on sensitive runs"
    if tool.risk == DANGEROUS and tool.name not in self.allow:
        return False, "dangerous tool not in allow-list (default-deny)"
    return True, "ok"
```

Three rules, in priority order:

1. **Privacy egress block** — on a `sensitive` run, *any* `network` tool is
   denied, regardless of allow-list. The privacy boundary wins. This is the
   same boundary that pins sensitive LLM calls to local models, extended to
   actions.
2. **Default-deny for DANGEROUS** — a dangerous tool runs only if its name was
   *explicitly* granted (`allow`). This is the sandbox's opt-in posture made
   universal: nothing dangerous happens unless someone said so by name.
3. **Allow the rest** — SAFE/MODERATE tools run; their safety comes from being
   built bounded (path jails, sandbox), not from asking permission each time.

Design rule: **risk lives on the tool, the decision lives in the policy.** A
new tool just declares its tier; it never re-implements gating. Swap the policy
(e.g. an interactive "ask the human" policy) without touching any tool.

## 4. The tool loop (ReAct, model-agnostic)

Native function-calling APIs are model- and endpoint-specific. This project
routes through a plain completion endpoint and must stay model-agnostic, so the
loop uses a **text protocol** the model drives, parsed with the same lenient
JSON extraction the verifier/planner use.

Contract given to the model:
- To act: reply with ONLY `{"tool": "<name>", "args": {...}}`.
- To finish: reply with ONLY `{"final": "<answer>"}`.

```
run_tool_loop(generate, task, registry, policy, max_steps) -> LoopResult

  catalog = descriptions of tools ALLOWED by the policy   # denied tools aren't even shown
  transcript = []
  for step in 1..max_steps:
      raw  = generate(prompt(task, catalog, transcript))
      data = extract_json(raw)
      if data has "final":            return final answer
      if data has "tool":
          tool = registry.get(name)
          if not tool:                obs = "unknown tool: <name>"
          else:
              ok, reason = policy.decide(tool)
              obs = reason            if not ok          # DENIED — not executed
              else  result = tool.run(args); obs = result.output or result.error
          transcript.append(action, obs)
      else:                           transcript.append(nudge to use the protocol)
  return best-effort final (last text / synthesized) + full transcript
```

Properties (mirror the verification loop):
- **Bounded** — hard `max_steps` ceiling; never loops forever.
- **Never raises** — tool exceptions become observations; unparseable model
  output becomes a protocol nudge.
- **Decoupled** — `generate` is an injected closure, so the loop is unit-tested
  with a fake generator and fake tools, no LLM, no real side effects.
- **Catalog reflects policy** — denied tools are omitted from the prompt, so the
  model isn't tempted to call what it can't use. The policy is still enforced at
  call time (defense in depth), not just by hiding.

## 5. Built-in tools (initial set)

| Tool | Risk | network | Notes |
|---|---|---|---|
| `python` | MODERATE | no | wraps `core/sandbox.run_python` — subprocess, timeout, temp cwd |
| `read_file` | SAFE | no | jailed to a root; `..` escapes are rejected |
| `write_file` | MODERATE | no | jailed to a work root; refuses to escape it |
| `web_fetch` | DANGEROUS | **yes** | HTTP GET → text; default-denied + blocked on sensitive runs |
| `shell` | DANGEROUS | no* | implemented for the tier demo; **not** in the default registry |

*`shell` can trivially egress (`curl`), so treat it as effectively networked
when composing a privacy policy; default-deny keeps it off unless granted.

**Path jail** (read/write): resolve the requested path against the tool's root
with `os.path.realpath` and reject anything that doesn't stay under the root.
This is the file-system analogue of the sandbox's temp-dir confinement.

## 6. Integration into this system

`agents/tool_agent.py` — `ToolAgent(BaseAgent)`:

```
class ToolAgent(BaseAgent):
    tools = []              # Tool instances this agent may use
    allow = []              # names of DANGEROUS tools explicitly granted
    max_tool_steps = 6

    def execute(self, task):
        registry = ToolRegistry(self.tools)
        policy   = Policy(allow=self.allow, sensitive=self.sensitive)
        generate = lambda prompt: query_llm(prompt, sensitive=self.sensitive)
        result   = run_tool_loop(generate, task_with_context, registry, policy, self.max_tool_steps)
        save_memory(...); return result.final
```

- Reuses the **whole existing pipeline**: routing/failover via `query_llm`,
  semantic context via `build_context`, auto-distillation + the verification
  gate via inherited `run()`. A tool-using agent is just an agent whose
  `execute` runs the loop instead of a single call.
- `sensitive=True` flows straight into the policy → network tools auto-denied
  *and* the LLM stays local. One flag, both boundaries.
- Existing agents are untouched (they don't subclass `ToolAgent`).

## 7. Where each piece lives

```
core/tools/base.py     Risk, ToolResult, Tool                         (pure)
core/tools/policy.py   Policy.decide                                  (pure)
core/tools/builtin.py  PythonTool, ReadFileTool, WriteFileTool, WebFetchTool, ShellTool
core/tools/loop.py     ToolRegistry, run_tool_loop, LoopResult
agents/tool_agent.py   ToolAgent(BaseAgent)
test_tools.py          policy matrix, path jail, sandbox tool, fetch gate, loop
```

## 8. Testing discipline

- Loop + policy are **offline/deterministic**: fake `generate` closure, fake
  tools, assert the policy decision and that denied tools are never executed.
- `python` tool gets a **real sandbox run** (the one component that must touch
  the OS). `read/write_file` run against a **temp dir** incl. a `..` escape that
  must be rejected. `web_fetch` is tested at the **policy gate** (denied by
  default / under sensitive) and with `requests.get` monkeypatched — **never a
  real network call in tests.**
- Add the suite to `run_tests.py`.

## 9. Design rules (carry to other systems)

1. **Risk on the tool, decision in the policy.** Centralize gating; never let a
   tool gate itself.
2. **Default-deny dangerous; allow by name.** New capabilities are off until
   someone explicitly grants them.
3. **Privacy egress is a hard, separate gate.** Sensitive runs forbid network
   tools outright — it outranks the allow-list.
4. **The loop is bounded, decoupled, and never raises.** Inject `generate`;
   cap steps; turn every failure into an observation.
5. **Hide what you deny.** Don't advertise tools the policy will refuse — but
   still enforce at call time (defense in depth).
6. **Reuse the agent pipeline.** Tools are an `execute()` strategy, not a parallel
   stack — they inherit routing, memory, verification, and distillation for free.

## 10. What this unlocks next

- **#7 feedback / eval loop:** tool transcripts + `Verdict` scores are the raw
  signal for the dormant `eval.jsonl` harness — now you can measure whether
  tool use actually improves task success, and prune tools that don't earn
  their risk.
- **Interactive permission policy:** swap `Policy` for one that escalates a
  DANGEROUS request to the human (reusing the escalation queue) instead of
  flat-denying — without touching a single tool.
