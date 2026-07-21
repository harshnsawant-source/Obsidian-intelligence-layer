# Obsidian Intelligence Layer (OIL)

A **local-first, privacy-preserving** multi-agent reasoning system built entirely
on free/local models (Ollama) — no paid APIs, no data leaving the device by
default. Agents share a semantic knowledge vault, reason through a
complexity-aware provider router, verify and self-correct their own output, and
answer over private notes and documents locally.

> **What this project really demonstrates:** not just that the system works, but
> a full engineering loop — *hypothesize → build → measure rigorously → accept a
> negative result → pivot.* I built a multi-agent orchestration system, then
> built a benchmark to test whether the orchestration actually helped. It didn't.
> So I followed the evidence and pivoted to the part that did. That story is
> below, and it's the most important thing in this repo.

> **About this repository.** The code here is a **public snapshot pinned at June
> 2026**, at the point the local-first knowledge layer first worked end to end.
> Development continued after that against my own private notes, and the working
> tree stayed private because it runs on my real vault. The section
> [*After this snapshot*](#after-this-snapshot-what-the-system-became) reports
> **measured outcomes** from that later work — results and design decisions, not
> code in this repo. Everything above it describes code you can read here.

---

## Engineering highlights

- **Heuristic complexity router** (`core/router.py`) — scores task complexity with
  cheap features (never an LLM-to-route-an-LLM tax), selects a provider, and fails
  over **circuit-breaker-aware** (cloud → local → graceful canned fallback). Treats
  a request *timeout* as a fast-open "severe" failure so a stalled local model is
  shed in one strike, not three.
- **Verification / self-correction loop** (`core/verification.py`, `verifiers.py`) —
  a pure `generate → verify → correct` loop with pluggable verifiers (schema,
  sandbox-executed code, critic). Output is always the verified attempt or the
  best of N.
- **Bounded code sandbox** (`core/sandbox.py`) — isolated subprocess, hard timeout,
  resource caps; honestly documented as *bounded, not OS-isolated*.
- **Risk-tiered tool framework** (`core/tools/`) — SAFE/MODERATE/DANGEROUS tiers,
  default-deny policy, path-jail, ReAct loop.
- **Semantic memory + RAG** — incremental, content-hashed embedding index
  (`nomic-embed-text`, local), cosine retrieval with keyword fallback; document
  ingestion (chunk → embed → retrieve) with SQLite metadata.
- **Structured shared-reasoning context** (`core/execution_context.py`) — typed
  findings/decisions/artifacts/risks/assumptions with provenance, dedup, consensus
  signals, and deterministic bounded rendering.
- **Output-health + degeneracy detection** (`core/output_health.py`) — catches
  repetition loops / no-answer output and treats it as a provider failure.
- **14 test suites, ~480 offline-deterministic checks** (`run_tests.py`) — every
  subsystem stubbed and tested without network or paid APIs.

## The experiment that defined the project: orchestration lift

The original thesis was that a *team of coordinated agents* would outperform a
single strong model call. Rather than assume it, I built an instrument to measure
it (`core/eval/`):

- **Orchestration-lift benchmark** — a fair, strong single-call baseline vs. the
  full pipeline, with **cost-adjusted, variance-gated significance** (lift must
  clear a noise floor, not just be positive), infra-failure exclusion, and grader
  reliability tagging.
- **Benchmark V2** — a falsifiable, three-arm design that isolates the two
  mechanisms cleanly:
  - **A** single call · **B** single call + verification loop · **C** verified
    planner (decomposition). Verification is held identical across B and C, so
    `C−B` measures decomposition and `B−A` measures verification.
  - **Anti-circularity:** public tests drive the verify loop; *hidden* tests grade
    (iteration can't teach to the test).
  - **Fractional, objective grading** (sandbox-executed, partial credit), an
    **independent calibration** pass that keeps only cases with genuine headroom,
    pre-registered statistics, **MDE reporting + Holm–Bonferroni** correction, and
    a unit-tested ability to return a clean **null**.

**The result:** on objectively-graded coding tasks, a single strong call already
scored ~1.0 — orchestration added **no measurable lift**, at large cost and
latency multiples. The benchmark did its job: it disproved the founding
assumption with evidence instead of vibes.

## The pivot: from "more agents" to "private knowledge, locally"

Following the evidence, the system pivoted to where the value actually was —
a private, local knowledge layer over the user's real notes:

- **Memory hygiene** — distillation happens once at the top level (not per
  subtask), with automatic curation, so retrieval quality doesn't decay.
- **Real Obsidian-vault ingestion** — recursive, incremental, with source-path +
  folder metadata; the user's raw notes are the immutable source of truth.
- **Privacy-tiered Q&A** — retrieval and a local-first answer never leave the
  device; sending anything to the cloud requires explicit, **informed,
  fail-closed, logged** consent (`core/consent.py`). Leak-rate is unit-tested to
  zero.

`coordination/` contains the design reviews and decision records from this
process — including the reviews that argued *against* shipping things.

---

## After this snapshot: what the system became

Work continued privately on my own vault. Reported here as **measured results**;
the code lives in a private tree.

**Retrieval quality is now a measured number, not a guess.** I built a
leakage-free retrieval benchmark over the real vault: each note is split into a
query half and a *disjoint* document half, and the system has to retrieve a
note's own doc-half out of a field of distractors — so a hit can't come from
overlapping text. Used it to run a head-to-head on embedding models at
**production note lengths** (not toy inputs):

| embedding model | top-1 | MRR |
|---|---|---|
| `nomic-embed-text` (previous) | 51.7% | 0.665 |
| `granite-embedding:278m` (current) | **73.3%** | **0.809** |

That's roughly **+22 points of top-1 accuracy** on the task the whole knowledge
layer rests on. Worth recording how nearly I got this wrong: my *first*
comparison used short inputs that fit both models comfortably, and granite looked
good. But 59% of my real notes are longer than granite's 512-token context, and
the index embeds whole notes — so the first result didn't describe production at
all. I threw it out and re-ran under the real regime before adopting anything.

**Swapping the embedder exposed a latent corruption bug.** The index reused
cached vectors keyed by content hash, with no notion of *which model* produced
them. Any embedder change would therefore have silently mixed two embedding
spaces in one index — cosine similarity between vectors from different models is
meaningless, and nothing would have crashed to tell me. The index now records its
model and forces a clean re-embed when it changes.

**Continuous research intake, with a hard human gate.** A daily digest pulls from
several sources, ranks them against what the system is actually built from, and
proposes improvements to itself in a *"what could make me better"* section.
Nothing self-applies — every proposal is a suggestion I accept or reject, and
each decision is logged and feeds back into the ranking. That gate is deliberate:
self-modifying agent architectures are the interesting failure mode, and this
system is explicitly not one.

**Every answer is auditable.** A single egress chokepoint keeps an always-on,
content-free log of any generation that leaves the device; per-answer receipts
record inputs, output and verdict by hash as a tamper-evident chain; and a
disposition ledger records whether I kept, edited or discarded each draft — which
turns "is this useful?" into an acceptance metric instead of an opinion.

**The automated code reviewer is itself held to account.** Findings from the
review pass are individually rated and recorded rather than applied on trust. In
practice most flagged "issues" turn out to be deliberate conventions the reviewer
misread — keeping that ledger is what stops a review loop from slowly rewriting a
codebase to satisfy a critic instead of a user.

**The test battery grew with it:** **45 suites / 1,388 offline-deterministic
checks**, still no network and no paid APIs.

---

## Run

```bash
pip install -r requirements.txt
ollama pull nomic-embed-text        # local embeddings
cd src && python main.py            # menu-driven
```
Menu highlights: **#14** run an agent (auto-routed), **#15** plan & execute,
**#16/#17** ingest / ask documents (local RAG), **#23/#24** index & ask your
Obsidian vault (local-first, consent-gated cloud), **#20** curate the vault,
**#22** run the lift benchmark.

## Tests

```bash
python run_tests.py     # 14 suites here, offline + deterministic
```

## Layout

```
src/agents/        thin agents; shared pipeline lives in BaseAgent
src/core/          router, memory/index, verification, sandbox, tools,
                   execution_context, vault_store, vault_qa, consent, eval/
src/configs/       paths + provider config (single source of truth)
src/knowledge/     the semantic distillation vault (agent-generated)
coordination/      design reviews + decision records (the process trail)
```

## Honest status

At this snapshot: a working prototype with strong safety and evaluation instincts
on prototype-grade infrastructure. The orchestration thesis is settled
(negative); the durable value is the local-first, privacy-preserving knowledge
layer, which is where all later work went. See
`coordination/PRODUCT_AUDIT_AND_ROADMAP.md` for the candid assessment.
