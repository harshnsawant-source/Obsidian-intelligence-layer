# Knowledge distillation — writes a curated lesson into the vault.
#
# Source fixes (Phase 7): this skill used to (a) name files by timestamp, so
# re-running the same task created duplicate notes; (b) copy the raw outcome in
# verbatim as the "Learning" (no actual distillation); and (c) happily save
# error/empty outcomes as "knowledge", poisoning retrieval. All three are fixed
# here so the curator (core/curator.py) cleans up far less after the fact.

import hashlib
from datetime import datetime

from core.llm_engine import query_llm
from core.curator import ERROR_MARKERS


def _looks_like_error(text):
    return any(marker in text for marker in ERROR_MARKERS)


def _distill_learning(task, outcome):

    # Turn the raw outcome into a concise, reusable lesson. Falls back to a
    # truncated outcome if the model is unavailable or returns the canned
    # fallback — distillation must never block on the LLM.

    prompt = (
        "Distill the key, reusable lesson from this task outcome into 1-3 "
        "concise sentences. State what works / what to do next time. No "
        "preamble.\n\n"
        f"Task:\n{task}\n\nOutcome:\n{outcome}\n\nLesson:"
    )

    try:
        summary = query_llm(prompt, max_tokens=300)
    except Exception:
        summary = ""

    summary = (summary or "").strip()

    if not summary or _looks_like_error(summary):
        # Graceful fallback: a trimmed version of the outcome itself.
        return outcome.strip()[:500]

    return summary


def execute(ctx, input_data):

    task = input_data.get("task", "")

    outcome = input_data.get("outcome", "")

    text = str(outcome or "")

    # Poison guard: never distill empty or error outcomes into the vault.
    if not text.strip():
        return {"skipped": "empty outcome"}

    if _looks_like_error(text):
        return {"skipped": "error outcome not distilled"}

    learning = _distill_learning(task, text)

    lesson = f"""

# Knowledge Distillation

Date:
{datetime.now()}

Task:
{task}

Outcome:
{outcome}

Learning:
{learning}

"""

    # Deterministic filename keyed on the (normalized) task: re-running the same
    # task OVERWRITES its note instead of creating a duplicate. Dedupe at source.
    key = " ".join(str(task or outcome).split()).lower()

    digest = hashlib.sha1(key.encode("utf-8")).hexdigest()[:16]

    filename = f"knowledge_{digest}.md"

    saved = ctx.knowledge.write(filename, lesson)

    return {"saved": saved, "learning": learning}
