import sys
import os
import tempfile

from core.tools.base import Tool, ToolResult, Risk
from core.tools.policy import Policy
from core.tools.loop import ToolRegistry, run_tool_loop
import core.tools.builtin as builtin
from core.tools.builtin import (
    PythonTool, ReadFileTool, WriteFileTool, WebFetchTool, ShellTool,
)

PASS = []
FAIL = []


def check(name, cond):
    (PASS if cond else FAIL).append(name)
    print(("PASS" if cond else "FAIL"), "-", name)


# ---- helper tools --------------------------------------------------------

class SafeEcho(Tool):
    name = "echo"
    risk = Risk.SAFE
    def run(self, args):
        return ToolResult(True, output=f"echo:{args.get('x')}")

class ModTool(Tool):
    name = "mod"
    risk = Risk.MODERATE
    def run(self, args):
        return ToolResult(True, output="moderate ok")

class DangerTool(Tool):
    name = "danger"
    risk = Risk.DANGEROUS
    def run(self, args):
        return ToolResult(True, output="boom")

class NetTool(Tool):
    name = "net"
    risk = Risk.SAFE          # low local risk but still egresses
    network = True
    def run(self, args):
        return ToolResult(True, output="fetched")

class RaisingTool(Tool):
    name = "raiser"
    risk = Risk.MODERATE
    def run(self, args):
        raise RuntimeError("kaboom")


# ---- Policy matrix -------------------------------------------------------

p = Policy()
check("policy: SAFE allowed by default", p.allows(SafeEcho()))
check("policy: MODERATE allowed by default", p.allows(ModTool()))
check("policy: DANGEROUS denied by default", p.allows(DangerTool()) is False)
check("policy: DANGEROUS allowed when granted by name",
      Policy(allow=["danger"]).allows(DangerTool()))

ps = Policy(sensitive=True)
check("policy: network tool denied on sensitive run", ps.allows(NetTool()) is False)
check("policy: network tool allowed when not sensitive", Policy().allows(NetTool()))
# Privacy outranks the allow-list:
check("policy: sensitive blocks network even if granted",
      Policy(allow=["net"], sensitive=True).allows(NetTool()) is False)
ok, reason = Policy().decide(DangerTool())
check("policy: denial gives a reason", ok is False and "default-deny" in reason)


# ---- ToolRegistry --------------------------------------------------------

reg = ToolRegistry([SafeEcho(), DangerTool(), NetTool()])
check("registry: get by name", reg.get("echo") is not None)
check("registry: unknown name -> None", reg.get("nope") is None)
allowed_default = {t.name for t in reg.allowed(Policy())}
check("registry: allowed() omits denied dangerous tool",
      "echo" in allowed_default and "danger" not in allowed_default)
allowed_sensitive = {t.name for t in reg.allowed(Policy(sensitive=True))}
check("registry: allowed() omits network tool when sensitive",
      "net" not in allowed_sensitive)


# ---- Tool loop -----------------------------------------------------------

def scripted(*replies):
    seq = list(replies)
    def gen(prompt):
        return seq.pop(0) if seq else '{"final": "ran out"}'
    return gen

# Test: a tool call then a final; observation is fed back
reg2 = ToolRegistry([SafeEcho()])
g = scripted('{"tool": "echo", "args": {"x": 42}}', '{"final": "done"}')
r = run_tool_loop(g, "t", reg2, Policy(), max_steps=5)
check("loop: completes with final", r.completed and r.final == "done")
check("loop: tool executed, observation captured",
      len(r.transcript) == 1 and r.transcript[0]["observation"] == "echo:42")

# Test: denied tool is NOT executed; observation explains the denial
reg3 = ToolRegistry([DangerTool()])
calls = {"n": 0}
class CountingDanger(DangerTool):
    def run(self, args):
        calls["n"] += 1
        return ToolResult(True, output="boom")
reg3 = ToolRegistry([CountingDanger()])
g = scripted('{"tool": "danger", "args": {}}', '{"final": "stopped"}')
r = run_tool_loop(g, "t", reg3, Policy(), max_steps=5)
check("loop: denied tool not executed", calls["n"] == 0)
check("loop: denial surfaced as observation",
      "DENIED" in r.transcript[0]["observation"])

# Test: unknown tool -> observation, no crash
g = scripted('{"tool": "ghost", "args": {}}', '{"final": "k"}')
r = run_tool_loop(g, "t", ToolRegistry([]), Policy(), max_steps=5)
check("loop: unknown tool reported", "unknown tool" in r.transcript[0]["observation"])

# Test: tool that raises -> observation, no crash
g = scripted('{"tool": "raiser", "args": {}}', '{"final": "k"}')
r = run_tool_loop(g, "t", ToolRegistry([RaisingTool()]), Policy(), max_steps=5)
check("loop: raising tool becomes observation",
      "tool error" in r.transcript[0]["observation"] and r.completed)

# Test: off-protocol output -> nudge, no crash
g = scripted("i am just chatting", '{"final": "ok"}')
r = run_tool_loop(g, "t", ToolRegistry([]), Policy(), max_steps=5)
check("loop: off-protocol nudged", "Respond with ONLY" in r.transcript[0]["observation"])

# Test: exhaustion is bounded and flagged
g = scripted('{"tool": "echo", "args": {}}', '{"tool": "echo", "args": {}}',
             '{"tool": "echo", "args": {}}')
r = run_tool_loop(g, "t", ToolRegistry([SafeEcho()]), Policy(), max_steps=3)
check("loop: bounded by max_steps", r.steps == 3 and r.completed is False)


# ---- Built-in: PythonTool (real sandbox) ---------------------------------

pt = PythonTool()
res = pt.run({"code": "print(6 * 7)"})
check("python tool: runs and returns stdout", res.ok and "42" in res.output)
res_bad = pt.run({"code": "raise ValueError('x')"})
check("python tool: failure reported", res_bad.ok is False and "ValueError" in res_bad.error)
check("python tool: empty code rejected", pt.run({"code": "  "}).ok is False)


# ---- Built-in: file tools (real temp dir + path jail) --------------------

workdir = tempfile.mkdtemp(prefix="oil_tools_test_")
try:
    wt = WriteFileTool(workdir)
    rt = ReadFileTool(workdir)

    w = wt.run({"path": "note.txt", "content": "hello tools"})
    check("write_file: writes ok", w.ok)
    r = rt.run({"path": "note.txt"})
    check("read_file: reads back content", r.ok and r.output == "hello tools")
    check("read_file: missing file reported", rt.run({"path": "nope.txt"}).ok is False)

    # Path jail: escaping the root must be refused for both read and write.
    check("read_file: path jail blocks escape",
          rt.run({"path": "../../etc/passwd"}).ok is False)
    check("write_file: path jail blocks escape",
          wt.run({"path": "../escape.txt", "content": "x"}).ok is False)
    check("file tools: SAFE/MODERATE risk tiers",
          rt.risk == Risk.SAFE and wt.risk == Risk.MODERATE)
finally:
    import shutil
    shutil.rmtree(workdir, ignore_errors=True)


# ---- Built-in: WebFetchTool (gated; network monkeypatched, never real) ---

wf = WebFetchTool()
check("web_fetch: DANGEROUS + network flags", wf.risk == Risk.DANGEROUS and wf.network)
check("web_fetch: rejects non-http url", wf.run({"url": "ftp://x"}).ok is False)

class FakeResp:
    text = "<html>ok</html>"
    def raise_for_status(self):
        pass

class FakeRequests:
    def get(self, url, timeout=None):
        return FakeResp()

builtin.requests = FakeRequests()  # ensure no real network call
# WebFetchTool imports requests lazily inside run(); inject into the module.
import sys as _sys
_sys.modules["requests"] = FakeRequests()
res = wf.run({"url": "http://example.com"})
check("web_fetch: returns body (network stubbed)", res.ok and "ok" in res.output)

# The gate: even though fetch *works*, the policy denies it by default and when sensitive.
reg_net = ToolRegistry([WebFetchTool()])
check("web_fetch: denied by default policy",
      Policy().allows(reg_net.get("web_fetch")) is False)
check("web_fetch: allowed only when granted",
      Policy(allow=["web_fetch"]).allows(reg_net.get("web_fetch")))
check("web_fetch: blocked on sensitive run even if granted",
      Policy(allow=["web_fetch"], sensitive=True).allows(reg_net.get("web_fetch")) is False)


# ---- ShellTool tier (not executed) ---------------------------------------

st = ShellTool()
check("shell: DANGEROUS + treated as egress-capable", st.risk == Risk.DANGEROUS and st.network)
check("shell: denied by default policy", Policy().allows(st) is False)


print(f"\n{len(PASS)} passed, {len(FAIL)} failed")
sys.exit(1 if FAIL else 0)
