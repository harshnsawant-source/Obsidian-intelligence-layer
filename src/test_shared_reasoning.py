import sys

from core.execution_context import SharedExecutionContext
from core.contributions import parse_contributions, build_instruction
import core.planner as pl
from core.planner import PlanExecutor

PASS = []
FAIL = []


def check(name, cond):
    (PASS if cond else FAIL).append(name)
    print(("PASS" if cond else "FAIL"), "-", name)


class FakeManager:
    def __init__(self, outputs=None):
        self.agents = {n: 1 for n in [
            "research-agent", "strategy-agent", "development-agent",
            "content-agent", "operations-agent", "retrieval-agent"]}
        self.calls = []
        self.outputs = outputs or {}

    def dispatch(self, name, task):
        self.calls.append((name, task))
        return self.outputs.get(name, f"OUTPUT[{name}]")


pl.route_agent = lambda task: "operations-agent"


# ===================== contribution protocol =====================

SAMPLE = (
    "Here is my analysis.\n"
    "```contributions\n"
    '{"findings":[{"finding":"Users prefer mobile","source":"survey","confidence":0.9}],'
    ' "risks":[{"risk":"Scope creep","severity":"high","mitigation":"freeze scope"}],'
    ' "assumptions":[{"assumption":"Budget is fixed","confidence":0.6}]}\n'
    "```"
)
parsed = parse_contributions(SAMPLE)
check("parse: findings extracted", len(parsed.get("findings", [])) == 1)
check("parse: risks extracted", parsed["risks"][0]["severity"] == "high")
check("parse: assumptions extracted",
      parsed["assumptions"][0]["assumption"] == "Budget is fixed")
check("parse: no block -> empty", parse_contributions("just text") == {})
check("parse: malformed entry dropped, valid kept",
      parse_contributions('```contributions\n{"findings":[{"x":1},{"finding":"ok"}]}\n```')
      ["findings"] == [{"finding": "ok"}])
check("build_instruction: empty -> empty", build_instruction([]) == "")
check("build_instruction: includes requested + protocol",
      "findings" in build_instruction(["findings"])
      and "contributions" in build_instruction(["findings"]))


# ===================== mutation APIs + dedup (#2, #3) =====================

ctx = SharedExecutionContext("goal")
ctx.add_finding("Users prefer mobile", "survey", 0.8, agent="research-agent")
ctx.add_finding("Users prefer mobile", "interviews", 0.9, agent="research-agent")
check("finding: exact dup merged into one record", len(ctx.findings) == 1)
check("finding: dup bumps support_count", ctx.findings[0]["support_count"] == 2)
check("finding: dup keeps max confidence", ctx.findings[0]["confidence"] == 0.9)
check("finding: dup records extra source", "interviews" in ctx.findings[0]["sources"])
ctx.add_finding("Mobile dominates usage", confidence=0.7)
check("finding: distinct accumulates", len(ctx.findings) == 2)
check("finding: deterministic ids", [f["id"] for f in ctx.findings] == ["f1", "f2"])


# ===================== decision provenance (#5) =====================

ctx.add_decision("Ship mobile first", reasoning="largest segment",
                 tradeoffs=["delays desktop"], agent="strategy-agent")
d = ctx.decisions[0]
check("decision: fields captured",
      d["decision"] == "Ship mobile first" and d["tradeoffs"] == ["delays desktop"])
check("decision: provenance agent + timestamp",
      d["agent"] == "strategy-agent" and bool(d["ts"]))


# ===================== artifact identity + versioning (#4) =====================

ctx.add_artifact("architecture", "v1 content", {"author": "dev"}, agent="development-agent")
ctx.add_artifact("architecture", "v2 content", agent="development-agent")
ctx.add_artifact("schema", "table defs")
check("artifact: versions accumulate under one id",
      len(ctx.artifact_versions("architecture")) == 2)
check("artifact: latest is v2",
      ctx.latest_artifact("architecture")["version"] == 2
      and ctx.latest_artifact("architecture")["content"] == "v2 content")
check("artifact: v1 coexists (history retained)",
      ctx.artifact_versions("architecture")[0]["content"] == "v1 content")
check("artifact: distinct type coexists",
      ctx.latest_artifact("schema")["version"] == 1)


# ===================== risk + optional assumption link (#6) =====================

aid = ctx.add_assumption("Traffic is mostly mobile", confidence=0.7, agent="research-agent")
ctx.add_risk("Desktop users underserved", severity="medium",
             mitigation="phase 2 desktop", agent="strategy-agent", assumption_id=aid)
r = ctx.risks[0]
check("risk: fields captured",
      r["severity"] == "medium" and r["mitigation"] == "phase 2 desktop")
check("risk: optional assumption link resolves",
      ctx.assumption_for_risk(r)["id"] == aid)
ctx.add_risk("Generic risk")
check("risk: link is optional (None when unlinked)",
      ctx.risks[1]["assumption_id"] is None)


# ===================== merge_contributions routing + provenance =====================

ctx2 = SharedExecutionContext("g2")
ctx2.merge_contributions(parsed, agent="research-agent")
check("merge: findings routed + stamped",
      len(ctx2.findings) == 1 and ctx2.findings[0]["agent"] == "research-agent")
check("merge: risks routed", len(ctx2.risks) == 1)
check("merge: assumptions routed", len(ctx2.assumptions) == 1)
ctx2.merge_contributions(None)
check("merge: non-dict input is safe", len(ctx2.findings) == 1)


# ===================== render_summary bounded + deterministic (#1) =====================

big = SharedExecutionContext("big goal")
for i in range(20):
    big.add_finding(f"finding number {i}", confidence=i / 20.0)
s1 = big.render_summary(max_items=5, max_chars=99999)
s2 = big.render_summary(max_items=5, max_chars=99999)
check("summary: deterministic", s1 == s2)
check("summary: findings capped to max_items", s1.count("[f") <= 5)
check("summary: ranked by confidence (top present, bottom absent)",
      "finding number 19" in s1 and "finding number 0" not in s1)
huge = SharedExecutionContext("g")
huge.add_finding("x" * 100, confidence=0.9)
for i in range(50):
    huge.record_output("a", "t", "Z" * 1000)
check("summary: hard char cap enforced",
      len(huge.render_summary(max_chars=2000)) <= 2000 + 60)
check("summary: empty context -> empty string",
      SharedExecutionContext("g").render_summary() == "")
check("render() alias == render_summary()", big.render() == big.render_summary())
check("render_full unbounded > summary for large ctx",
      len(huge.render_full()) > len(huge.render_summary()))


# ===================== distillation digest excludes transient (#7) =====================

dctx = SharedExecutionContext("g")
dctx.record_output("research-agent", "task", "RAW_OUTPUT_SHOULD_NOT_DISTILL")
dctx.add_finding("Key insight", confidence=0.9)
dctx.add_finding("Weak guess", confidence=0.2)
dctx.add_risk("Critical risk", severity="high")
dctx.add_risk("Minor nit", severity="low")
dig = dctx.distillation_digest()
check("digest: includes key finding", "Key insight" in dig)
check("digest: excludes low-confidence finding", "Weak guess" not in dig)
check("digest: includes major risk", "Critical risk" in dig)
check("digest: excludes minor risk", "Minor nit" not in dig)
check("digest: excludes raw outputs", "RAW_OUTPUT_SHOULD_NOT_DISTILL" not in dig)


# ===================== serialization round-trip (#8 Phase-6 seam) =====================

snapshot = ctx.to_dict()
rt = SharedExecutionContext.from_dict(snapshot)
check("serialize: findings preserved", len(rt.findings) == len(ctx.findings))
check("serialize: artifact versions preserved",
      rt.latest_artifact("architecture")["version"] == 2)
check("serialize: counters preserved", rt._counters == ctx._counters)
check("serialize: dedup index preserved",
      rt._finding_keys == ctx._finding_keys)


# ===================== PlanExecutor accumulates + propagates structure =====================

outs = {
    "research-agent": ('Research done.\n```contributions\n'
                       '{"findings":[{"finding":"Mobile usage is high","confidence":0.9}]}\n```'),
    "strategy-agent": ('Strategy set.\n```contributions\n'
                       '{"decisions":[{"decision":"Mobile-first","reasoning":"data","tradeoffs":["x"]}]}\n```'),
}
fm = FakeManager(outputs=outs)
plan = [{"task": "research market", "agent": "research-agent"},
        {"task": "set strategy", "agent": "strategy-agent"}]
ex_ctx = PlanExecutor(manager=fm).run("launch", plan)
check("executor: findings accumulated from output + provenance",
      len(ex_ctx.findings) == 1 and ex_ctx.findings[0]["agent"] == "research-agent")
check("executor: decisions accumulated from output + provenance",
      len(ex_ctx.decisions) == 1 and ex_ctx.decisions[0]["agent"] == "strategy-agent")
strategy_task = [t for n, t in fm.calls if n == "strategy-agent"][0]
check("executor: prior finding PROPAGATED into later step",
      "Mobile usage is high" in strategy_task)
check("executor: raw outputs still recorded", len(ex_ctx.outputs) == 2)


# ===================== backward compatibility (text-only agents) =====================

fm2 = FakeManager()  # default OUTPUT[name], no contribution blocks
ex2 = PlanExecutor(manager=fm2).run("g", [{"task": "x", "agent": "content-agent"}])
check("compat: no contributions -> empty structured buckets",
      ex2.findings == [] and ex2.decisions == []
      and ex2.risks == [] and ex2.assumptions == [])
check("compat: outputs still recorded", len(ex2.outputs) == 1)


print(f"\n{len(PASS)} passed, {len(FAIL)} failed")
sys.exit(1 if FAIL else 0)
