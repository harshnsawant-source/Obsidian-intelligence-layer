import sys
import os
import json
import tempfile
import shutil
from pathlib import Path

from core.eval.graders import (
    make_grader, contains_grader, exact_grader, regex_grader,
)
import core.eval.harness as harness
from core.eval.harness import EvalCase, run_eval, load_cases
import core.embeddings as embeddings
from core import curator
from core.curator import scan_vault, apply_plan

PASS = []
FAIL = []


def check(name, cond):
    (PASS if cond else FAIL).append(name)
    print(("PASS" if cond else "FAIL"), "-", name)


# ---- graders -------------------------------------------------------------

check("contains: hit", contains_grader("42")("t", "the answer is 42").ok)
check("contains: miss", contains_grader("42")("t", "nope").ok is False)
check("contains: all needles required",
      contains_grader(["a", "z"])("t", "only a here").ok is False)
check("exact: normalized match", exact_grader("Hello World")("t", "  hello   world ").ok)
check("exact: mismatch", exact_grader("a")("t", "b").ok is False)
check("regex: match", regex_grader(r"\d{3}")("t", "code 404").ok)
check("regex: no match", regex_grader(r"\d{3}")("t", "none").ok is False)

# schema grader via make_grader
sg = make_grader({"grader": "schema", "required_keys": ["name", "age"]})
check("schema grader: valid", sg("t", '{"name":"Ada","age":36}').ok)
check("schema grader: missing key", sg("t", '{"name":"Ada"}').ok is False)

# code grader via make_grader (real sandbox)
cg = make_grader({"grader": "code", "test": "assert add(2,3)==5\nprint('ok')"})
check("code grader: passing code", cg("t", "```python\ndef add(a,b):\n    return a+b\n```").ok)
check("code grader: failing code",
      cg("t", "```python\ndef add(a,b):\n    return a-b\n```").ok is False)

# unknown grader
try:
    make_grader({"grader": "bogus"})
    check("make_grader: unknown raises", False)
except ValueError:
    check("make_grader: unknown raises", True)


# ---- harness -------------------------------------------------------------

specs = [
    {"id": "c1", "task": "say 42", "grader": "contains", "expected": "42"},
    {"id": "c2", "task": "say hi", "grader": "exact", "expected": "hi"},
    {"id": "c3", "task": "fail me", "grader": "contains", "expected": "WONTAPPEAR"},
]
cases = [EvalCase(s) for s in specs]

# run_fn returns the task's trailing token; deterministic, offline.
def fake_run(task):
    return {"say 42": "the answer: 42", "say hi": "hi", "fail me": "oops"}[task]

report = run_eval(cases, fake_run, label="unit", persist=False)
check("harness: counts cases", report.n == 3)
check("harness: pass_rate correct (2/3)", abs(report.pass_rate - 2/3) < 1e-9)
check("harness: per-case ok flags",
      [r.ok for r in report.results] == [True, True, False])
check("harness: render shows summary", "2/3 passed" in report.render())

# crashing run_fn -> recorded as failed case, not raised
def boom_run(task):
    raise RuntimeError("kaboom")
rep2 = run_eval([EvalCase({"id": "x", "grader": "contains", "expected": "a"})],
                boom_run, label="crash", persist=False)
check("harness: crashing run_fn becomes failed case",
      rep2.n == 1 and rep2.results[0].ok is False and "run error" in rep2.results[0].output)

# load_cases from a temp jsonl (with comment + blank + malformed line)
tmpdir = tempfile.mkdtemp(prefix="oil_eval_")
try:
    cf = Path(tmpdir) / "c.jsonl"
    cf.write_text(
        '# comment\n'
        '{"id":"a","grader":"contains","expected":"x"}\n'
        '\n'
        'not json\n'
        '{"id":"b","grader":"exact","expected":"y"}\n',
        encoding="utf-8",
    )
    loaded = load_cases(cf)
    check("load_cases: skips comments/blanks/bad lines", len(loaded) == 2)

    # persistence: append a summary line to a redirected eval_runs file
    saved = harness.EVAL_RUNS
    harness.EVAL_RUNS = Path(tmpdir) / "eval_runs.jsonl"
    try:
        run_eval(cases, fake_run, label="persisted", persist=True)
        rows = [json.loads(l) for l in harness.EVAL_RUNS.read_text(encoding="utf-8").splitlines() if l.strip()]
        check("harness: run persisted to history",
              len(rows) == 1 and rows[0]["label"] == "persisted" and rows[0]["n"] == 3)
    finally:
        harness.EVAL_RUNS = saved
finally:
    shutil.rmtree(tmpdir, ignore_errors=True)


# ---- curator: prune + exact dedupe (offline) -----------------------------

vault = tempfile.mkdtemp(prefix="oil_vault_")
def w(name, content):
    p = os.path.join(vault, name)
    with open(p, "w", encoding="utf-8") as fh:
        fh.write(content)
    return p

try:
    GOOD1 = "# Note\nA detailed lesson about designing resilient agent routers and failover."
    GOOD2 = "# Note\nAn entirely different lesson about embeddings and cosine retrieval ranking."
    w("good1.md", GOOD1)
    w("good2.md", GOOD2)
    w("err.md", "# Knowledge\nLLM ERROR: HTTPConnectionPool ... Max retries exceeded")
    w("empty.md", "   \n\n  ")
    w("dupA.md", "# Note\nThis exact lesson is duplicated verbatim across two files here.")
    w("dupB.md", "# Note\nThis exact lesson is duplicated verbatim across two files here.")

    plan = scan_vault(vault=vault, near_dupes=False)

    prune_names = {os.path.basename(p["file"]) for p in plan.prune}
    check("curator: prunes error note", "err.md" in prune_names)
    check("curator: prunes empty note", "empty.md" in prune_names)
    check("curator: does not prune good notes",
          "good1.md" not in prune_names and "good2.md" not in prune_names)

    exact_groups = [g for g in plan.dup_groups if g["kind"] == "exact"]
    check("curator: finds one exact-dup group", len(exact_groups) == 1)
    drops = exact_groups[0]["drop"] if exact_groups else []
    check("curator: dup group drops exactly one of the pair", len(drops) == 1)
    check("curator: plan.to_delete = 2 prune + 1 dup", len(plan.to_delete) == 3)

    # apply
    deleted = apply_plan(plan, vault=vault)
    remaining = {f for f in os.listdir(vault)}
    check("curator: apply deleted 3 files", len(deleted) == 3)
    check("curator: error+empty gone", "err.md" not in remaining and "empty.md" not in remaining)
    check("curator: good notes kept", "good1.md" in remaining and "good2.md" in remaining)
    check("curator: exactly one of the dup pair kept",
          ("dupA.md" in remaining) ^ ("dupB.md" in remaining))
finally:
    shutil.rmtree(vault, ignore_errors=True)


# ---- curator: near-dup via stubbed embeddings ----------------------------

vault2 = tempfile.mkdtemp(prefix="oil_vault2_")
def w2(name, content):
    with open(os.path.join(vault2, name), "w", encoding="utf-8") as fh:
        fh.write(content)

try:
    # Two notes with DIFFERENT text (different hashes) but near-identical
    # meaning; a third on another topic. Stub embeddings by topic keyword.
    w2("alpha1.md", "# Note\nScaling the platform horizontally with stateless workers. variant one.")
    w2("alpha2.md", "# Note\nScaling the platform horizontally with stateless workers. variant two differs.")
    w2("beta.md", "# Note\nWriting clear launch announcement copy for a product release event.")

    def fake_embed(text, *a, **k):
        return [1.0, 0.0] if "Scaling the platform" in text else [0.0, 1.0]
    embeddings.embed_text = fake_embed

    plan2 = scan_vault(vault=vault2, near_dupes=True)
    near_groups = [g for g in plan2.dup_groups if g["kind"] == "near"]
    check("curator: finds a near-dup group", len(near_groups) == 1)
    if near_groups:
        names = {os.path.basename(near_groups[0]["keep"])} | {
            os.path.basename(d) for d in near_groups[0]["drop"]}
        check("curator: near group is the two alpha notes",
              names == {"alpha1.md", "alpha2.md"})
        check("curator: beta note not grouped", len(near_groups[0]["drop"]) == 1)
finally:
    shutil.rmtree(vault2, ignore_errors=True)


# ---- curator: apply refuses to delete outside the vault ------------------

safe_dir = tempfile.mkdtemp(prefix="oil_safe_")
outside = tempfile.mkdtemp(prefix="oil_outside_")
try:
    victim = os.path.join(outside, "important.md")
    with open(victim, "w", encoding="utf-8") as fh:
        fh.write("do not delete me")
    rogue = curator.CurationPlan()
    rogue.prune.append({"file": victim, "reason": "test"})
    deleted = apply_plan(rogue, vault=safe_dir)
    check("curator: refuses to delete outside vault",
          deleted == [] and os.path.exists(victim))
finally:
    shutil.rmtree(safe_dir, ignore_errors=True)
    shutil.rmtree(outside, ignore_errors=True)


# ---- knowledge_distill source fixes --------------------------------------

from capability.core.skill_loader import load_skill

distill = load_skill("knowledge_distill")
distill.query_llm = lambda *a, **k: "Concise distilled lesson."  # stub, no live call

class FakeKnowledge:
    def __init__(self):
        self.writes = {}
    def write(self, filename, content):
        self.writes[filename] = content
        return filename

class FakeCtx:
    def __init__(self):
        self.knowledge = FakeKnowledge()

# error outcome is skipped (poison guard)
ctx = FakeCtx()
r = distill.execute(ctx, {"task": "x", "outcome": "LLM ERROR: connection refused"})
check("distill: error outcome skipped", r.get("skipped") and not ctx.knowledge.writes)

# empty outcome skipped
ctx = FakeCtx()
r = distill.execute(ctx, {"task": "x", "outcome": "   "})
check("distill: empty outcome skipped", r.get("skipped") and not ctx.knowledge.writes)

# canned router fallback skipped
ctx = FakeCtx()
r = distill.execute(ctx, {"task": "x", "outcome": "[orchestrator] All providers are unavailable"})
check("distill: canned fallback skipped", bool(r.get("skipped")))

# normal outcome -> saved, learning is the distilled summary (not verbatim)
ctx = FakeCtx()
r = distill.execute(ctx, {"task": "Build a thing", "outcome": "It works and here is a long enough outcome to matter."})
check("distill: normal outcome saved", "saved" in r and len(ctx.knowledge.writes) == 1)
check("distill: learning is distilled, not a verbatim copy",
      r["learning"] == "Concise distilled lesson.")

# deterministic filename: same task -> same file (dedupe at source)
ctx1, ctx2 = FakeCtx(), FakeCtx()
distill.execute(ctx1, {"task": "Same Task", "outcome": "first run outcome content here"})
distill.execute(ctx2, {"task": "same   task", "outcome": "second run different content here"})
f1 = list(ctx1.knowledge.writes)[0]
f2 = list(ctx2.knowledge.writes)[0]
check("distill: same task -> same filename (dedupe at source)", f1 == f2)
ctx3 = FakeCtx()
distill.execute(ctx3, {"task": "A Different Task", "outcome": "different task outcome content"})
f3 = list(ctx3.knowledge.writes)[0]
check("distill: different task -> different filename", f3 != f1)


print(f"\n{len(PASS)} passed, {len(FAIL)} failed")
sys.exit(1 if FAIL else 0)
