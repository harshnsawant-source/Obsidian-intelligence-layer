# Verification & Self-Correction — Design Blueprint

> Reusable blueprint. This describes a **generate → verify → correct** layer for
> any agent/orchestration system, then how this project wires it in. The
> abstractions (`Verdict`, `Verifier`, `refine`) are deliberately independent of
> this codebase so they can be lifted into other systems unchanged.

## 1. The problem this solves

A bare LLM agent is **single-shot**: it generates once and the output is taken
as truth. Two failures follow:

1. **Unchecked output.** Wrong code, malformed JSON, hand-wavy reasoning all
   pass straight through.
2. **The learning loop amplifies mistakes.** When outputs are distilled into a
   knowledge store and later retrieved as context, an unverified wrong answer
   gets *re-fed* into future prompts. Errors **compound**; the memory substrate
   degrades silently with use.

Verification turns "guess once" into "produce → check → fix → recheck until
correct," and **gates what is allowed to become memory**. Closing this gate is
the single highest-leverage change: it stops the compounding-error failure mode
at its source.

## 2. Core abstractions

Three pieces. Keep them small and dependency-free so they port anywhere.

### 2.1 `Verdict`
The result of checking one (task, output) pair.

```
Verdict(ok: bool, score: float in [0,1], feedback: str, source: str)
```
- `ok` — did it pass.
- `score` — graded quality/confidence; used to keep the **best** attempt when
  no attempt fully passes.
- `feedback` — concrete, actionable description of what's wrong. This text is
  fed back into the next generation, so it must be specific (a stderr trace, a
  schema error, a critic's list of issues) — not "try harder."
- `source` — which verifier produced it (for logging/telemetry).

### 2.2 `Verifier`
A pluggable check. Two methods:

```
applies(task, output, meta) -> bool      # cheap gate: is this verifier relevant?
check(task, output, meta)   -> Verdict   # the actual judgement
```
`applies()` lets you attach many verifiers and have each opt in by content
(e.g. the code verifier only fires when the output contains a code block).

A verifier is **pure with respect to the loop**: it never mutates state, never
regenerates — it only judges. This keeps verifiers trivially testable.

### 2.3 `refine` — the loop
The orchestrator. It is given a **generation closure**, not an agent, so it is
fully decoupled:

```
refine(generate, task, verifiers, max_tries, meta) -> RefineResult

  generate(feedback: str|None, previous: str|None) -> str
```

Algorithm:

```
output = generate(None, None)
if no applicable verifiers:
    return RefineResult(output, verdict=None, ok=True, attempts=1)   # back-compat no-op

best = None
for attempt in 1..max_tries:
    verdict = aggregate(applicable_verifiers, task, output, meta)
    best = max(best, (output, verdict), key=score)
    if verdict.ok:
        return RefineResult(output, verdict, ok=True, attempts=attempt)
    if attempt < max_tries:
        output = generate(verdict.feedback, output)   # correction pass
return RefineResult(best.output, best.verdict, ok=False, attempts=max_tries)
```

Guarantees:
- **Every returned output has been verified** (including the last correction).
- **No verifiers ⇒ exactly one call, no behavior change** — verification is
  strictly additive; legacy paths are untouched.
- **Never raises, never loops forever** — bounded by `max_tries`; on exhaustion
  returns the highest-scoring attempt (graceful degradation, same philosophy as
  the LLM router's canned floor).

### 2.4 Aggregation (multiple verifiers)
When several verifiers apply: **AND** semantics — all must pass. `feedback` is
concatenated; `score` is the minimum. One failing check fails the verdict and
its feedback drives the retry.

## 3. The verifier catalogue

Ordered by ROI. Each maps to a distinct output shape.

| Verifier | Output shape | How it checks | Feedback on failure |
|---|---|---|---|
| **SchemaVerifier** | structured / JSON | parse + required-keys | parse error / missing keys |
| **CodeVerifier** | code | run in sandbox (+ optional tests) | stderr / non-zero exit / timeout |
| **CriticVerifier** | prose / reasoning | 2nd LLM call reviews against the task | the critic's itemised issues |

- **SchemaVerifier** formalises the ad-hoc ```` ```json ````-fence repair that
  structured callers otherwise hand-roll. Cheap, deterministic, no LLM.
- **CodeVerifier** is where verification and *tools* converge: you cannot
  "check code" without **executing** it, and execution is the first real tool.
  This is why verification and a sandboxed execution capability are one build,
  not two phases. It is **opt-in** (off by default) because running
  model-generated code is the genuine risk surface — see §4.
- **CriticVerifier** costs a second model call. It's free on the cloud model
  but doubles latency, so it is **opt-in per agent / per planner run**, not a
  global default. Best-of-N is a variant (sample N, keep the highest-scored)
  for when revision is weaker than reselection.

## 4. Sandbox safety model (the part to copy carefully)

Executing model-generated code is the only component here with a real attack
surface. The model is **bounded execution, not true isolation** — state that
plainly so downstream systems don't over-trust it.

**What `run_python` guarantees (portable, std-lib only):**
- Runs in a **separate subprocess** (`sys.executable -I`), never `exec()` in
  the host process — a crash/`sys.exit` can't take down the orchestrator.
- **Isolated mode (`-I`)**: ignores env vars and user site-packages, so the
  child can't inherit ambient config/credentials via the usual channels.
- **Hard timeout** → the process is killed (`TimeoutExpired`) and reported as a
  failure, not a hang.
- **Throwaway temp working directory**, deleted afterwards — file writes don't
  touch the project tree.
- **Output capped** (stdout/stderr truncated) so a runaway print can't blow up
  memory or the context window.

**What it deliberately does NOT guarantee (and must be documented for reuse):**
- **No network isolation.** Blocking sockets portably from pure Python is not
  possible. For untrusted code, wrap the call in an OS-level sandbox: a
  container, `firejail` (Linux), or Windows Sandbox.
- **No CPU/memory caps on Windows.** `resource` limits are Unix-only; on Linux
  the blueprint sets `RLIMIT_CPU`/`RLIMIT_AS` in a `preexec_fn`. On Windows we
  rely on the timeout alone. (This project runs on Windows → timeout-bounded.)

**Permission posture:** code execution is **off unless explicitly enabled** by
the caller (`CodeVerifier(execute=True)` / an agent opt-in flag). Default-deny
is the safety layer the roadmap called for *before* a general tool framework:
the first "tool" (run code) ships already gated.

## 5. Integration into this system

### 5.1 BaseAgent — verification in the unified pipeline
`query_agent` already does `build_context → query_llm → save → return`. The LLM
call becomes a `refine(...)` call with a generation closure that re-issues the
prompt with appended feedback:

```
def generate(feedback, previous):
    p = base_prompt
    if feedback:
        p += correction_block(previous, feedback)   # "your last attempt failed because…"
    return query_llm(p, sensitive=self.sensitive)

result = refine(generate, task, self.verifiers, self.max_verify_tries)
self.last_verdict = result.verdict
```

- `BaseAgent.verifiers = []` and `max_verify_tries = 2` by default ⇒ **every
  existing agent is byte-for-byte unchanged** (no verifiers → single call).
- An agent opts in by declaring `verifiers = [...]` — that's the whole API.

### 5.2 The distillation gate (the poisoning fix)
`run()` distills only when verification did not fail:

```
if self.last_verdict is None or self.last_verdict.ok:
    distill(...)
else:
    log: "skipped distillation — output failed verification"
```

`None` (no verifier ran) preserves today's behavior; a **failed** verdict keeps
bad output out of the vault. This is the line that stops error compounding.

### 5.3 Planner
`Planner(verify=True)` attaches a `CriticVerifier` to the **synthesis** step
(the consolidated final answer is the highest-value, lowest-frequency call —
the right place to spend a second model pass). Default `verify=False` keeps the
existing planner path and its tests unchanged. The decompose step's bespoke
JSON-repair is the SchemaVerifier pattern in miniature; it stays as-is but is
documented as the same idea.

## 6. Where each piece lives

```
core/verification.py   Verdict, Verifier, aggregate, refine, RefineResult   (pure)
core/sandbox.py        ExecResult, run_python                                (std-lib only)
core/verifiers.py      SchemaVerifier, CodeVerifier, CriticVerifier
agents/base_agent.py   refine wired into query_agent; distillation gated in run()
core/planner.py        optional verify=True → critic on synthesis
test_verification.py   loop + verifiers + sandbox + distillation-gate coverage
```

## 7. Testing discipline (same as the rest of the project)

- The loop and verifiers are **offline + deterministic**: inject a fake
  `generate` closure and fake verifiers; stub `verifiers.query_llm` for the
  critic. Stubs accept `*args, **kwargs`.
- The sandbox gets **one real execution** check (trivial Python) plus a timeout
  check — it's the one component that must touch the OS to be meaningful.
- The distillation gate is tested by asserting distill is called on a passing
  verdict and **not** called on a failing one.

## 8. Design rules (carry these to other systems)

1. **The loop owns retries; verifiers only judge.** Don't let a verifier
   regenerate — that tangles concerns and defeats testability.
2. **Feedback must be concrete.** The retry is only as good as the error text
   you feed back. A stack trace beats "the code is wrong."
3. **Verification is additive and bounded.** No verifiers ⇒ no change; always a
   `max_tries` ceiling; always return the best attempt, never raise.
4. **Gate the memory, not just the answer.** The highest-value use of a verdict
   is deciding what becomes long-term knowledge.
5. **Executing generated code is opt-in and bounded.** Ship it default-deny;
   be explicit that bounded ≠ isolated.
6. **Spend the second LLM pass where it pays** — synthesis and final answers,
   not every intermediate step.

## 9. What this unlocks next

- **Tool framework (#6):** `run_python` is the first gated tool; the same
  permission posture (default-deny, explicit enable) generalises to file/web/
  shell tools.
- **Feedback / eval loop (#7):** `Verdict.ok/score` is the pass/fail signal the
  dormant `eval.jsonl` harness needs to *measure* whether verification and
  tools actually raise quality — closing the loop from "we built it" to "we can
  prove it helps."
