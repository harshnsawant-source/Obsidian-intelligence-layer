import re
import sys
import shutil
import hashlib
import tempfile
from pathlib import Path

import core.memory_index as mi
from core.memory_index import MemoryIndex
import core.embeddings as emb


PASS = []
FAIL = []


def check(name, cond):
    (PASS if cond else FAIL).append(name)
    print(("PASS" if cond else "FAIL"), "-", name)


# --- deterministic offline embedder (bag-of-words over a fixed dim) ---
DIM = 32


def fake_embed(text):
    fake_embed.calls += 1
    vec = [0.0] * DIM
    for word in re.findall(r"[a-z]+", (text or "").lower()):
        idx = int(hashlib.md5(word.encode()).hexdigest(), 16) % DIM
        vec[idx] += 1.0
    return vec if any(vec) else None


fake_embed.calls = 0
mi.embed_text = fake_embed


# --- temp vault + index so we never touch real data ---
tmp = Path(tempfile.mkdtemp())
vault = tmp / "vault"
vault.mkdir()
index_path = tmp / "index" / "vault_index.json"

(vault / "a.md").write_text(
    "database scaling and performance tuning for high traffic systems",
    encoding="utf-8")
(vault / "b.md").write_text(
    "marketing content writing and social media post scheduling",
    encoding="utf-8")

idx = MemoryIndex(vault=vault, index_path=index_path)

# Test 1: existing vault notes get indexed + persisted locally
stats = idx.ensure_index()
check("existing vault notes are indexed",
      stats["total"] == 2 and stats["added"] == 2)
check("index persisted to local json", index_path.exists())

# Test 2a: re-run indexes nothing (incremental, hash-based)
fake_embed.calls = 0
stats = idx.ensure_index()
check("incremental: unchanged files not re-embedded",
      fake_embed.calls == 0 and stats["added"] == 0 and stats["updated"] == 0)

# Test 2b: modify one file -> exactly one re-embed
fake_embed.calls = 0
(vault / "a.md").write_text(
    "database sharding, replication and performance at massive scale",
    encoding="utf-8")
stats = idx.ensure_index()
check("incremental: changed file re-embedded once",
      stats["updated"] == 1 and stats["added"] == 0 and fake_embed.calls == 1)

# Test 2c: add a new file
(vault / "c.md").write_text(
    "kubernetes deployment pipeline and service reliability",
    encoding="utf-8")
stats = idx.ensure_index()
check("incremental: new file added", stats["added"] == 1 and stats["total"] == 3)

# Test 2d: remove a file -> dropped from index
(vault / "b.md").unlink()
stats = idx.ensure_index()
check("incremental: removed file dropped",
      stats["removed"] == 1 and stats["total"] == 2)

# Test 3: similarity ranking + scores
res = idx.search("database performance and scaling", k=5, min_score=0.0)
check("ranking: results sorted by score desc",
      res == sorted(res, key=lambda r: r["score"], reverse=True))
check("ranking: most relevant note ranked first",
      bool(res) and res[0]["file"].endswith("a.md"))
check("ranking: float similarity scores attached",
      bool(res) and isinstance(res[0]["score"], float))

# Test 3b: min_score filters weak matches
res_thr = idx.search("database performance and scaling", k=5, min_score=0.25)
check("min_score filters weak matches",
      all(r["score"] >= 0.25 for r in res_thr))

# Test 4: fallback when embeddings fail
mi.embed_text = lambda text: None
res_fb = idx.search("database", k=5)
check("fallback used when embeddings fail",
      bool(res_fb) and res_fb[0].get("fallback") is True
      and res_fb[0]["score"] is None)
mi.embed_text = fake_embed  # restore

# Test 4b: embedding cache (efficiency) — success cached, failure retried
_real_one = emb._embed_one
ecalls = {"n": 0}
emb._embed_cache.clear()
emb._embed_one = lambda t, m: (ecalls.__setitem__("n", ecalls["n"] + 1)
                               or [1.0, 2.0, 3.0])
v1 = emb.embed_text("same query")
v2 = emb.embed_text("same query")
check("embed cache: identical text embedded once", ecalls["n"] == 1 and v1 == v2)
emb.embed_text("different query")
check("embed cache: new text triggers a fresh embed", ecalls["n"] == 2)
emb._embed_cache.clear()
emb._embed_one = lambda t, m: (ecalls.__setitem__("n", ecalls["n"] + 1)
                               or None)
ecalls["n"] = 0
emb.embed_text("flaky")
first = ecalls["n"]
emb.embed_text("flaky")
check("embed cache: failures are NOT cached (retried on recovery)",
      ecalls["n"] > first)
emb._embed_one = _real_one
emb._embed_cache.clear()

# Test 5: paraphrase retrieval (LIVE — needs Ollama embeddings; else skip)
live = emb.embed_text("connectivity probe")
if live is not None:
    ltmp = Path(tempfile.mkdtemp())
    lv = ltmp / "vault"
    lv.mkdir()
    (lv / "scale.md").write_text(
        "The platform must scale to handle a surge in concurrent users.",
        encoding="utf-8")
    (lv / "cooking.md").write_text(
        "A recipe for baking sourdough bread with a crispy crust.",
        encoding="utf-8")
    mi.embed_text = emb.embed_text  # real embeddings for the live check
    lidx = MemoryIndex(vault=lv, index_path=ltmp / "idx.json")
    lres = lidx.search(
        "improve throughput and capacity under heavy load",
        k=2, min_score=0.0)
    check("paraphrase retrieval (live): scaling note ranked first",
          bool(lres) and lres[0]["file"].endswith("scale.md"))
    shutil.rmtree(ltmp, ignore_errors=True)
else:
    print("SKIP - paraphrase retrieval (live): embeddings endpoint not reachable")

# --- cleanup ---
shutil.rmtree(tmp, ignore_errors=True)

print(f"\n{len(PASS)} passed, {len(FAIL)} failed")
sys.exit(1 if FAIL else 0)
