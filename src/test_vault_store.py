import sys
import os
import tempfile
import shutil
from pathlib import Path

import core.memory_index as mi
from core.memory_index import MemoryIndex
from core.vault_store import VaultStore

PASS = []
FAIL = []


def check(name, cond):
    (PASS if cond else FAIL).append(name)
    print(("PASS" if cond else "FAIL"), "-", name)


# Deterministic, content-sensitive embedding stub (one-hot over tag markers) so
# indexing populates and cosine search ranks predictably — no Ollama needed.
_TAGS = ["ALPHA", "BETA", "GAMMA", "DELTA", "EPSILON"]


def fake_embed(text):
    text = text or ""
    return [1.0 if t in text else 0.0 for t in _TAGS]


mi.embed_text = fake_embed


vault = tempfile.mkdtemp(prefix="oil_vaultstore_")
idx_path = Path(tempfile.mkdtemp(prefix="oil_vaultidx_")) / "notes_index.json"


def w(rel, content):
    p = Path(vault) / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(content, encoding="utf-8")


try:
    w("root.md", "ALPHA root note")
    w("docs/d1.md", "BETA docs note")
    w("daily-ops/log.md", "GAMMA daily note")
    w("projects/x.md", "DELTA excluded project note")          # excluded dir
    w("docs/generated_export.md", "EPSILON generated export")  # excluded name

    before_files = sum(len(fs) for _, _, fs in os.walk(vault))

    store = VaultStore(vault=vault, index_path=idx_path)
    stats = store.reindex()

    indexed = {os.path.basename(e["file"]) for e in store.index.entries}
    check("vault: recursive discovery finds nested notes",
          {"root.md", "d1.md", "log.md"} <= indexed)
    check("vault: excluded dir (projects) skipped", "x.md" not in indexed)
    check("vault: generated/export name skipped", "generated_export.md" not in indexed)
    check("vault: exactly the 3 in-scope notes indexed", len(indexed) == 3)

    # Source-path + folder metadata.
    r_alpha = store.search("ALPHA", k=5)
    check("vault: search returns the matching note", len(r_alpha) == 1
          and os.path.basename(r_alpha[0]["source"]) == "root.md")
    check("vault: root note folder is (root)", r_alpha[0]["folder"] == "(root)")

    r_beta = store.search("BETA", k=5)
    check("vault: docs note folder derived from path",
          r_beta and r_beta[0]["folder"] == "docs")
    check("vault: result carries source path",
          r_beta and r_beta[0]["source"].endswith("d1.md"))

    # Folder-scoped retrieval.
    check("vault: folder filter excludes other folders",
          store.search("BETA", k=5, folder="daily-ops") == [])
    r_scoped = store.search("GAMMA", k=5, folder="daily-ops")
    check("vault: folder filter keeps matching folder",
          r_scoped and r_scoped[0]["folder"] == "daily-ops")

    check("vault: folders() lists distinct top-level folders",
          set(store.folders()) == {"(root)", "docs", "daily-ops"})

    # Non-destructive: indexing wrote nothing into the vault.
    after_files = sum(len(fs) for _, _, fs in os.walk(vault))
    check("vault: indexing did not write into the vault", after_files == before_files)

    # Regression: DEFAULT MemoryIndex (non-recursive, no excludes) is unchanged
    # -> only the top-level note is seen (distillation vault / docs unaffected).
    reg_idx = Path(tempfile.mkdtemp(prefix="oil_regidx_")) / "reg.json"
    default_index = MemoryIndex(vault=vault, index_path=reg_idx)
    default_index.ensure_index()
    default_seen = {os.path.basename(e["file"]) for e in default_index.entries}
    check("vault: default MemoryIndex stays non-recursive (backward-compatible)",
          default_seen == {"root.md"})
    shutil.rmtree(reg_idx.parent, ignore_errors=True)

finally:
    shutil.rmtree(vault, ignore_errors=True)
    shutil.rmtree(idx_path.parent, ignore_errors=True)


print(f"\n{len(PASS)} passed, {len(FAIL)} failed")
sys.exit(1 if FAIL else 0)
