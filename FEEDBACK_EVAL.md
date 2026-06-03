# Feedback & Evaluation Loop — Design Blueprint

> Reusable blueprint. Closes the learning loop: a system that *acts* and
> *remembers* must also be able to **measure whether it is getting better** and
> **curate what it has learned**. The pieces (`Grader`, eval harness,
> vault curator) are decoupled and lift into other systems unchanged.

## 1. What this solves (grounded in what was actually broken)

Earlier phases added capability (tools), reliability (verification), and memory
(distillation/RAG). But two gaps remained, and both were real, not theoretical:

1. **No measurement.** The per-skill `eval.jsonl` files were bare stubs
   (`{"test":"basic"}`) that nothing ran. There was no way to answer "did this
   change make the system better or worse?" — so every improvement was a guess.
2. **An unmanaged, polluting memory.** Distillation wrote one vault note per run
   with a **timestamp filename** and copied the raw outcome in verbatim. Result:
   re-running a task **duplicates** notes, and failures got saved as
   "knowledge" — e.g. a real vault note whose entire content was
   `LLM ERROR: ...connection refused`. The verification gate (Phase 3) stops
   *new* poison at the source, but it doesn't measure quality and doesn't clean
   what's already there.

The feedback loop is the missing half of "learning": **signal → measure → act.**

```
   ┌─────────────┐     ┌──────────────┐     ┌──────────────────┐
   │  SIGNAL     │ ──▶ │  MEASURE     │ ──▶ │  ACT             │
   │ Verdict /   │     │ eval harness │     │ curate the vault │
   │ grader      │     │ (tracked     │     │ (prune + dedupe) │
   │ pass/score  │     │  over runs)  │     │                  │
   └─────────────┘     └──────────────┘     └──────────────────┘
          ▲                                          │
          └──────────── better memory ◀──────────────┘
```

## 2. Signal: graders (reuse, don't reinvent)

A **grader** answers "is this output correct for this task?" — exactly what a
`Verifier` does. So graders *are* verifiers: `grade(task, output) -> Verdict`
(reusing the Phase-3 `Verdict(ok, score, feedback)`). This is the keystone
decision — the same component that drives self-correction at runtime also
scores evals offline. No parallel grading stack.

Grader kinds (a case names one):

| Grader | Scores by | Backed by |
|---|---|---|
| `contains` | output contains expected substring(s) | text check |
| `exact` | normalized exact match | text check |
| `regex` | output matches a pattern | text check |
| `code` | code runs + passes a hidden test | `CodeVerifier` + sandbox |
| `schema` | output is valid JSON with required keys | `SchemaVerifier` |

`code` is the highest-signal grader: pass/fail is **objective and free** (the
sandbox is the grader — no LLM judge needed, no API cost).

## 3. Measure: the eval harness

A case set is JSONL; one case per line:

```
{"id": "primes", "task": "...", "grader": "code", "test": "assert solve()==1060"}
{"id": "json",   "task": "...", "grader": "schema", "required_keys": ["steps"]}
{"id": "fact",   "task": "...", "grader": "contains", "expected": "Ada Lovelace"}
```

```
run_eval(cases, run_fn, label) -> EvalReport

  run_fn(task) -> str            # INJECTED: an agent, query_llm, a plan — anything
  for case in cases:
      output  = run_fn(case.task)
      verdict = case.grader(case.task, output)
      record CaseResult(id, verdict.ok, verdict.score, output)
  EvalReport: pass_rate, mean_score, n, per-case results
  persist a one-line summary to runtime/eval_runs.jsonl   # trend over time
```

Properties:
- **`run_fn` is injected** → the harness is unit-tested with a fake runner (no
  LLM), and the *same* harness evaluates a single model call, a tool agent, or a
  full plan. The thing under test is a parameter, not baked in.
- **Persisted history** (`runtime/eval_runs.jsonl`, one summary line per run)
  turns eval into a **regression gate**: compare today's pass-rate to
  yesterday's to prove (or disprove) that a change helped. This is the entire
  point — "we built it" becomes "we measured that it helps."
- **Never raises**: a crashing `run_fn` for one case is recorded as a failed
  case, not a dead run.

## 4. Act: the vault curator

Quality signal applied *to the memory itself*. Two operations, both
**dry-run by default** (scan returns a plan; nothing is deleted until
`apply_plan` is called):

### 4.1 Prune (remove negative-value notes)
Drop notes that are worse than nothing because they pollute retrieval:
- **Error captures** — content matching failure markers (`LLM ERROR`, the
  router's canned-fallback string, `Traceback`, `Max retries exceeded`).
- **Empty / trivial** — no real content after stripping the template.

This directly cleans the poison the verification gate can't reach (notes written
before the gate existed, or by paths that bypass it).

### 4.2 Dedupe (collapse redundant notes)
- **Exact** — identical normalized content (SHA-1) → keep one. Deterministic,
  offline; catches the timestamp-filename re-run duplicates.
- **Near** — embedding cosine ≥ threshold (reuses the local embedding client)
  → keep the most informative (longest), drop the rest. Skipped gracefully when
  embeddings are unavailable (exact-dedupe still runs).

Safety rules (carry these — deleting memory is irreversible):
- Operates **only** within the knowledge vault dir; never outside.
- **Dry-run first**: `scan_vault()` returns a `CurationPlan` (prunes + dup
  groups, each with a reason); a human/caller reviews, then `apply_plan()`.
- A file marked for prune is never also counted as a dedupe "drop" (no
  double-reasoning).
- After applying, the semantic index drops removed files on its next
  incremental pass — no stale vectors.

## 5. Where each piece lives

```
core/eval/graders.py   Grader kinds -> callables returning Verdict (reuse verifiers)
core/eval/harness.py   load_cases, run_eval, EvalReport, persist to eval_runs.jsonl
core/eval/cases.jsonl  the starter eval set (code / schema / contains)
core/curator.py        scan_vault -> CurationPlan ; apply_plan  (prune + dedupe)
main.py                menu: Run Eval Suite ; Curate Vault (dry-run -> confirm)
test_feedback.py       graders, harness (fake run_fn), curator (temp vault, stub embed)
```

## 6. Testing discipline

- Graders + harness are **offline/deterministic**: a fake `run_fn` returns
  canned outputs; assert per-case verdicts, pass-rate, and that a crashing
  case is recorded (not raised). The `code` grader gets one **real sandbox** run.
- Curator runs against a **temp vault dir** with planted dupes + error notes;
  embeddings are **stubbed** so near-dedupe is deterministic and offline. Assert
  the plan, then assert `apply_plan` deletes exactly the planned files and keeps
  the rest. Never touch the real vault in tests.

## 7. Design rules (carry to other systems)

1. **Graders are verifiers.** One definition of "correct," used both to
   self-correct at runtime and to score evals. Never fork them.
2. **Inject the thing under test.** The harness evaluates whatever `run_fn` you
   give it; it doesn't know about agents. That keeps eval reusable across the
   whole stack.
3. **Persist every run.** A single pass-rate is noise; the *trend* across runs
   is the signal. Append-only history makes eval a regression gate.
4. **Curation is dry-run first, scoped, and reasoned.** Memory deletion is
   irreversible — always produce a reviewable plan with a reason per file before
   touching disk.
5. **Prefer free, objective graders.** Sandbox/exec and schema graders cost
   nothing and don't drift; reserve LLM-judge graders for genuinely subjective
   quality.

## 8. What this closes / unlocks

- **Closes the learning loop:** the system can now *measure* its own quality and
  *curate* its own memory — not just accumulate it.
- **Unlocks principled iteration:** every future change (a new model, a prompt
  tweak, a new tool) can be A/B'd against `eval_runs.jsonl` instead of guessed.
- **Natural next steps:** a richer eval set; an LLM-judge grader for subjective
  tasks; wiring distillation to write content-hashed filenames (prevent dupes at
  the source, complementing the curator that cleans them after the fact).
