import re
import sys
import hashlib
import tempfile
from pathlib import Path

import core.memory_index as mi
import core.document_store as ds
import core.db as db
import core.escalation as esc
from agents.base_agent import BaseAgent
from agents.retrieval_agent import RetrievalAgent

PASS = []
FAIL = []


def check(name, cond):
    (PASS if cond else FAIL).append(name)
    print(("PASS" if cond else "FAIL"), "-", name)


# --- deterministic offline embedder (bag-of-words) ---
DIM = 32


def fake_embed(text):
    vec = [0.0] * DIM
    for w in re.findall(r"[a-z]+", (text or "").lower()):
        vec[int(hashlib.md5(w.encode()).hexdigest(), 16) % DIM] += 1.0
    return vec if any(vec) else None


mi.embed_text = fake_embed

# --- redirect all stores to temp ---
tmp = Path(tempfile.mkdtemp())
ds.DOCUMENTS_DIR = tmp / "docs"
ds.DOC_INDEX = tmp / "docidx.json"
db.DB_PATH = tmp / "t.sqlite"
esc.ESCALATIONS = tmp / "esc.md"

store = ds.DocumentStore()

# Test 1: chunking with overlap
chunks = store._chunk("x" * 4000)
check("chunking: long text splits into multiple chunks", len(chunks) > 1)

# Test 2: ingest writes chunks + registers in SQLite
doc = tmp / "notes.txt"
doc.write_text(
    "The migration runbook covers database failover and rollback steps. " * 60,
    encoding="utf-8")
info = store.ingest(str(doc))
chunk_files = list((tmp / "docs").glob("notes__chunk*.md"))
check("ingest: chunk files written", len(chunk_files) == info["chunks"] > 0)
docs = store.documents()
check("ingest: registered in SQLite", len(docs) == 1 and docs[0]["title"] == "notes.txt")

# Test 3: semantic search finds the document content
hits = store.search("database failover rollback", k=3)
check("doc search: returns hits", len(hits) >= 1)
check("doc search: hit points at a chunk file",
      bool(hits) and "notes__chunk" in hits[0]["file"])

# Test 4: re-ingest replaces, no duplicate registry rows
store.ingest(str(doc))
check("re-ingest: single registry row (no dupes)", len(store.documents()) == 1)

# Test 5: sensitivity flags
check("sensitive: BaseAgent default False", BaseAgent.sensitive is False)
check("sensitive: RetrievalAgent pinned local", RetrievalAgent.sensitive is True)

# Test 6: escalation surface
esc.record_escalation("design a distributed consensus protocol", 0.9)
text = esc.list_escalations()
check("escalation: recorded and listable",
      "distributed consensus" in text and "0.90" in text)

import shutil
shutil.rmtree(tmp, ignore_errors=True)

print(f"\n{len(PASS)} passed, {len(FAIL)} failed")
sys.exit(1 if FAIL else 0)
