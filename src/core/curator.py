# Vault curator: applies the quality signal to the memory itself. Prunes
# negative-value notes (errors, empties) and collapses duplicates (exact +
# near). Dry-run by default — scan_vault() returns a reviewable plan; nothing
# is deleted until apply_plan(). Operates ONLY within the vault dir. See
# FEEDBACK_EVAL.md section 4.

import os
import hashlib

from configs.paths import KNOWLEDGE_VAULT, EMBED_INPUT_CHAR_LIMIT
from core.log import get_logger

log = get_logger("curator")

# Notes whose content matches a failure marker are worse than nothing — they
# pollute retrieval. Drop them.
ERROR_MARKERS = (
    "LLM ERROR",
    "[orchestrator] All providers",      # router canned fallback
    "Traceback (most recent call last)",
    "Max retries exceeded",
    "Failed to establish a new connection",
)

# Below this many non-whitespace chars (after the template), a note carries no
# real knowledge.
MIN_CONTENT_CHARS = 40

# Cosine at/above this counts as a near-duplicate.
NEAR_DUP_THRESHOLD = 0.95


class CurationPlan:

    def __init__(self):
        self.prune = []            # list of {"file", "reason"}
        self.dup_groups = []       # list of {"keep", "drop":[...], "kind"}

    @property
    def to_delete(self):
        files = [p["file"] for p in self.prune]
        for g in self.dup_groups:
            files.extend(g["drop"])
        return files

    def render(self):
        lines = [
            f"Curation plan: {len(self.prune)} to prune, "
            f"{sum(len(g['drop']) for g in self.dup_groups)} duplicates to drop "
            f"({len(self.dup_groups)} groups)."
        ]
        for p in self.prune:
            lines.append(f"  PRUNE  {os.path.basename(p['file'])}  — {p['reason']}")
        for g in self.dup_groups:
            lines.append(
                f"  DEDUP[{g['kind']}] keep {os.path.basename(g['keep'])}; drop "
                + ", ".join(os.path.basename(d) for d in g["drop"])
            )
        return "\n".join(lines)


def _note_files(vault):
    if not os.path.isdir(vault):
        return []
    return sorted(
        os.path.join(vault, f)
        for f in os.listdir(vault)
        if f.endswith(".md")
    )


def _read(path):
    try:
        with open(path, "r", encoding="utf-8", errors="replace") as fh:
            return fh.read()
    except Exception:
        return ""


def _is_error(content):
    return any(m in content for m in ERROR_MARKERS)


def _content_len(content):
    return len("".join(content.split()))


def _hash(content):
    return hashlib.sha1(" ".join(content.split()).encode("utf-8")).hexdigest()


def _cosine(a, b):
    import numpy as np
    va, vb = np.array(a, dtype=float), np.array(b, dtype=float)
    na, nb = np.linalg.norm(va), np.linalg.norm(vb)
    if na == 0 or nb == 0 or va.shape != vb.shape:
        return 0.0
    return float(va.dot(vb) / (na * nb))


def scan_vault(vault=None, near_dupes=True):

    # Build a dry-run CurationPlan. near_dupes=True adds embedding-based
    # near-duplicate detection (skipped automatically if embeddings are down).

    vault = str(vault or KNOWLEDGE_VAULT)

    plan = CurationPlan()

    files = _note_files(vault)

    contents = {f: _read(f) for f in files}

    # --- prune ---------------------------------------------------------
    pruned = set()
    for f in files:
        c = contents[f]
        if _is_error(c):
            plan.prune.append({"file": f, "reason": "error capture"})
            pruned.add(f)
        elif _content_len(c) < MIN_CONTENT_CHARS:
            plan.prune.append({"file": f, "reason": "empty / trivial"})
            pruned.add(f)

    survivors = [f for f in files if f not in pruned]

    # --- exact dedupe (hash) -------------------------------------------
    by_hash = {}
    for f in survivors:
        by_hash.setdefault(_hash(contents[f]), []).append(f)

    deduped = set()
    for group in by_hash.values():
        if len(group) > 1:
            keep = _pick_keeper(group, contents)
            drop = [f for f in group if f != keep]
            plan.dup_groups.append({"keep": keep, "drop": drop, "kind": "exact"})
            deduped.update(drop)

    # --- near dedupe (embeddings) --------------------------------------
    if near_dupes:
        remaining = [f for f in survivors if f not in deduped]
        _add_near_dupes(plan, remaining, contents, deduped)

    return plan


def _pick_keeper(group, contents):
    # Keep the most informative (longest); tie-break by earliest mtime.
    return max(group, key=lambda f: (_content_len(contents[f]), -os.path.getmtime(f)))


def _add_near_dupes(plan, files, contents, already_dropped):

    from core.embeddings import embed_text

    vecs = {}
    for f in files:
        v = embed_text(contents[f][:EMBED_INPUT_CHAR_LIMIT])
        if v:
            vecs[f] = v

    if len(vecs) < 2:
        return  # embeddings unavailable or too few — exact dedupe still applied

    keys = list(vecs)
    grouped = set()

    for i, fi in enumerate(keys):
        if fi in grouped or fi in already_dropped:
            continue
        cluster = [fi]
        for fj in keys[i + 1:]:
            if fj in grouped or fj in already_dropped:
                continue
            if _cosine(vecs[fi], vecs[fj]) >= NEAR_DUP_THRESHOLD:
                cluster.append(fj)
        if len(cluster) > 1:
            keep = _pick_keeper(cluster, contents)
            drop = [f for f in cluster if f != keep]
            plan.dup_groups.append({"keep": keep, "drop": drop, "kind": "near"})
            grouped.update(cluster)


def auto_curate(vault=None, near_dupes=True):

    # Non-interactive curation for the AGENT-DISTILLATION vault: scan + apply in
    # one call. Safe to run on startup. IMPORTANT: only ever point this at the
    # distillation/scratch vault (KNOWLEDGE_VAULT) — never at the user's real
    # notes; pruning + near-dup removal is acceptable for agent-generated lessons
    # but would be destructive for hand-written notes. Best-effort: never raises.
    try:
        plan = scan_vault(vault, near_dupes=near_dupes)
        deleted = apply_plan(plan, vault)
        if deleted:
            log.info("auto-curate removed %d notes", len(deleted))
        return {"deleted": len(deleted), "plan": plan}
    except Exception as error:
        log.warning("auto-curate skipped: %s", error)
        return {"deleted": 0, "plan": None}


def apply_plan(plan, vault=None):

    # Delete the planned files — irreversible. Refuses to touch anything outside
    # the vault dir. Returns the list of deleted paths.

    vault_real = os.path.realpath(str(vault or KNOWLEDGE_VAULT))

    deleted = []

    for path in plan.to_delete:
        real = os.path.realpath(path)
        if real != vault_real and not real.startswith(vault_real + os.sep):
            log.warning("refusing to delete outside vault: %s", path)
            continue
        try:
            os.remove(real)
            deleted.append(real)
        except FileNotFoundError:
            continue
        except Exception as error:
            log.warning("could not delete %s: %s", path, error)

    log.debug("curator removed %d notes", len(deleted))

    return deleted
