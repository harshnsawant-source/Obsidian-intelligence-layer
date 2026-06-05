# K-C MVP: answer questions over the real Obsidian vault, local-first.
#
# Privacy contract (one egress point):
#   retrieve()          - no LLM call            -> cannot leave the device
#   extractive_answer() - no LLM call            -> cannot leave the device
#   local_synthesis()   - query_llm(sensitive=True) -> router pins LOCAL only
#   cloud_synthesis()   - the ONLY path that leaves; records consent BEFORE the
#                         send (fail-closed), then query_llm(prefer_cloud=True)
#
# No routing/planner/orchestration changes — this only composes existing pieces
# (VaultStore retrieval, query_llm with the existing sensitive/prefer_cloud flags,
# output_health, consent logging).

from core.llm_engine import query_llm
from core.router import CANNED_FALLBACK
from core.output_health import is_failed_output
from core.vault_store import VaultStore
from core.consent import record_consent


# Keep the local prompt small so the 4B floor is not overloaded.
MAX_PASSAGES = 4
SNIPPET_CHARS = 600
SYNTH_MAX_TOKENS = 800


def retrieve(query, k=5, folder=None, store=None):
    store = store or VaultStore()
    return store.search(query, k=k, folder=folder)


def extractive_answer(passages):
    # Pure formatting of retrieved notes. No LLM call -> fully local, never fails.
    if not passages:
        return "No matching notes found in your vault."

    lines = ["Most relevant notes:"]
    for p in passages:
        score = p.get("score")
        label = f"{score:.3f}" if score is not None else "keyword"
        snippet = (p.get("snippet") or "").strip().replace("\n", " ")[:SNIPPET_CHARS]
        lines.append(f"\n[{label}] {p.get('folder')}/  {p.get('source')}")
        if snippet:
            lines.append(f"    {snippet}")
    return "\n".join(lines)


def _context_block(passages):
    blocks = []
    for p in passages[:MAX_PASSAGES]:
        snippet = (p.get("snippet") or "").strip()[:SNIPPET_CHARS]
        blocks.append(f"[source: {p.get('source')}]\n{snippet}")
    return "\n\n".join(blocks)


def _prompt(query, passages):
    return (
        "Answer the question using ONLY the notes below. Cite the source path(s) "
        "you used. If the notes do not contain the answer, say so plainly.\n\n"
        f"Notes:\n{_context_block(passages)}\n\n"
        f"Question: {query}\n\nAnswer:"
    )


def local_synthesis(query, passages):
    # Local-only synthesis. Returns (text, ok); ok=False on degenerate/failed
    # output so the caller falls back to the extractive answer. sensitive=True is
    # the leak guard (the router never routes a sensitive call to the cloud).
    if not passages:
        return None, False

    text = query_llm(_prompt(query, passages), sensitive=True,
                     max_tokens=SYNTH_MAX_TOKENS)

    failed, _ = is_failed_output(text, extra_markers=(CANNED_FALLBACK,))
    if failed:
        return None, False

    return text, True


def cloud_synthesis(query, passages):
    # The ONLY path that sends private content off-device. Fail-closed: consent is
    # recorded FIRST; if logging raises, the exception propagates and NO send
    # happens. Callers must have obtained explicit, informed user consent before
    # calling this.
    prompt = _prompt(query, passages)
    sources = [p.get("source") for p in passages[:MAX_PASSAGES]]

    record_consent(query, sources, len(prompt))   # raises -> caller aborts send

    return query_llm(prompt, prefer_cloud=True, max_tokens=SYNTH_MAX_TOKENS)
