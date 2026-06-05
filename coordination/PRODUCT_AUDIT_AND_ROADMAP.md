# OIL — Product Audit & Knowledge-Work Roadmap

- **Author:** Claude (Executor)
- **Date:** 2026-06-06
- **Mandate:** Pivot from code-orchestration benchmarking back to the product:
  knowledge retrieval, memory quality, note intelligence. Benchmark findings are
  treated as **settled** (strong models one-shot coding; orchestration adds little
  measurable lift there; routing + reliability are the real wins).
- **Scope:** audit + roadmap only. No code changed.

## 1. Architecture vs. original vision

Vision (per the skill/README): a local-first system whose agents *share a semantic
knowledge vault, auto-distill their outputs, and answer over private documents*, with
no paid APIs and no single point of failure.

| Vision claim | Reality | Verdict |
| :--- | :--- | :--- |
| Semantic knowledge vault | `MemoryIndex` (incremental embed + cosine + keyword fallback) over `src/knowledge/vault` | ✅ works |
| Auto-distill agent outputs | `BaseAgent.run` → `knowledge_distill` every run | ⚠️ works but **pollutes** (per-subtask, dup-prone) |
| Answer over private documents | `DocumentStore` RAG (#16 ingest, #17 ask) | ⚠️ works but **manual per-file ingest only** |
| "Obsidian" intelligence | **Not connected to the real Obsidian vault** — the indexed "vault" is the internal distillation store; your actual notes are never read unless manually ingested one file at a time | ❌ **major gap** |
| No single point of failure | Effectively a single-cloud-model system; local 4B floor times out/loops and rarely produces usable output for non-trivial work | ❌ aspirational |
| Local for privacy | `sensitive=True` pins to local 4B — so the **most valuable work (over private notes) runs on the weakest engine** | ⚠️ correct-but-painful |

**Headline:** the engine (router, memory index, RAG, distillation) is solid, but it is
pointed at a **self-built scratch vault**, not the user's real knowledge — and the one
auto-writer it has (distillation) is degrading that vault's quality. The product's actual
value (intelligence over *your* notes) is the least-built part.

## 2. Highest-impact production issues (knowledge-work)

| # | Issue | Why it hurts the product |
| :--- | :--- | :--- |
| K1 | **Real Obsidian vault not ingested** (manual per-file only) | The richest knowledge source — the user's notes — is invisible to the system. This is the core value, missing. |
| K2 | **Distillation pollution (CU7)** | Per-subtask, per-run distillation floods the vault with low-value/duplicate notes → retrieval signal-to-noise drops over time. Quality of memory *is* the product. |
| K3 | **Sensitive→local-4B bottleneck** | Synthesis over private notes (the core use case) runs on the model that times out/loops. Capability where it matters most is worst. |
| K4 | **No real synthesis/connection layer** | Today: top-k retrieval (#6) + doc-RAG (#17). No cross-note synthesis, no link/connection surfacing — the differentiated Obsidian value. |
| K5 | **Retrieval-delegate latency** | development-agent (and the delegate pattern) call retrieval (local) on every run → 28–120s tax; the delegate path is fragile. |
| K6 | **Curation is manual + memory seams unused** | Curator runs only via menu #20; `episodes` table + `SharedExecutionContext.to_dict` retrieval seam are unused → no cross-run memory. |

## 3. Prioritized fixes

### P0 — memory quality (do first; directly fixes the product)
- **CU7 (production distillation policy).** Distill **once**, at the **top-level task** only, **after verification**, and **only if novel** (skip near-duplicates of existing vault notes — reuse the curator's cosine check). Suppress distillation for subtask/delegated runs. *Effect:* stops vault pollution at the source → retrieval quality stops degrading. Highest ROI.
- **Auto-curation.** Run `curator.scan_vault` automatically (e.g., after N distillations or on startup) instead of only menu #20. *Effect:* compounding cleanup.

### P1 — connect to the real knowledge (unlocks the actual product)
- **Ingest the real Obsidian vault.** Add incremental ingestion of the user's `.md` notes (the existing `MemoryIndex` incremental embed already supports this — point it at the real vault dir, watch mtimes). Keep distilled notes in a *separate* namespace so agent scratch never overwrites user notes. *Effect:* the system finally reasons over the user's actual knowledge.
- **Unified retrieval** across {user notes, ingested documents, distilled memory} with source tagging, so an answer cites where it came from.

### P2 — capability for private work + synthesis (the hard, differentiated part)
- **Privacy tiers for sensitive work (K3).** Default local for private; add an **explicit user-consent path** to send a specific query/notes to the free cloud model for capability (the user decides per-query). Plus make the local path *reliable* even when used: anti-repetition cutoff + short timeout + tighter prompts (partial answer beats a 120s hang). *Effect:* the core private-notes use case stops being bottlenecked by a broken 4B.
- **Synthesis & connections (K4).** Extend doc-RAG into "ask over your whole knowledge base," and add link/connection surfacing (suggest related notes / `[[links]]`) — the uniquely-Obsidian value.
- **Retrieval-delegate fix (K5).** Make the retrieval delegate conditional (skip when the task is self-contained); for non-private context allow cloud. *Effect:* faster, more reliable agent runs.

### P3 — cross-run memory (later)
- Wire the unused `episodes` table + `SharedExecutionContext` serialization into retrievable cross-run memory, so the system *remembers* prior sessions.

## 4. Roadmap (knowledge-work value, not code benchmarks)

1. **Phase K-A — Memory hygiene (P0):** CU7 production distillation policy + auto-curation. *Measurable:* vault duplicate-rate and note count over time (structural metrics, no LLM judge).
2. **Phase K-B — Real-vault ingestion (P1):** incremental ingest of the Obsidian vault + unified, source-tagged retrieval. *Measurable:* retrieval relevance (see §6).
3. **Phase K-C — Private-work capability (P2/K3):** reliability hardening for local + explicit cloud-consent tier.
4. **Phase K-D — Synthesis & connections (P2/K4):** knowledge-base Q&A + related-note surfacing.
5. **Phase K-E — Cross-run memory (P3).**

Each phase ships a *product* capability; orchestration is invoked only where it has already
earned its place (verification on checkable outputs), per settled evidence.

## 5. Benchmark stance (settled)

- Coding orchestration-lift is **answered (negative)**; no further code-benchmark phases.
- The system's value = **cheapest-sufficient routing + reliability**, both already delivered.

## 6. If any new benchmark — it must serve the product

The old benchmark measured code (gradeable but off-mission). A **product-relevant** benchmark
measures **retrieval quality**, which is objectively gradeable without an LLM judge:
- **Retrieval-relevance benchmark:** a small hand-labeled corpus (notes + queries with known
  relevant notes) → measure precision@k / recall@k of `MemoryIndex` retrieval, and the effect
  of CU7/curation on signal-to-noise. *This directly supports K1/K2/K4* — it tells us whether
  the system surfaces the right knowledge, which is the actual product question.
- **Memory-quality metrics** (structural, no judge): duplicate-rate, dead-note-rate, vault
  growth vs. unique-information growth.
- **Synthesis quality** (answer correctness over notes) genuinely needs a cross-model judge →
  **defer** until a judge exists; do not gate roadmap on it.

**Rule going forward:** propose a benchmark only when it answers a question that changes a
*product* decision (retrieval relevance, memory quality). No more measuring code generation.

## Recommendation

Start with **Phase K-A (CU7 + auto-curation)** — it's the highest-ROI, lowest-risk fix, it
directly improves the product (memory quality), and it pays down debt we already identified.
Then **K-B (real-vault ingestion)**, which is what makes this an *Obsidian* intelligence layer
rather than a self-talking scratchpad. Confirm scope before implementation, per process.
