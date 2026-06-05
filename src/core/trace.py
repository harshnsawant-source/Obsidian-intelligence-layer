import json
import time
from collections import deque
from pathlib import Path

from configs.paths import RUNTIME


# Minimal per-call observability — deliberately NOT a tracing platform.
#
# A single bounded in-memory ring of structured records, optionally mirrored to
# runtime/trace.jsonl. The router (core/router.py) is the one chokepoint every
# LLM call passes through, so it emits exactly one record per generate(). That is
# enough to answer the questions that mattered during the Phase A sweep — "which
# subtask went to which provider, did it fail over, how long did it take?" —
# without instrumenting every call site or building spans/UI.
#
# Contract: recording is purely additive. It never affects the value the router
# returns and never raises (disk writes are best-effort).


TRACE_FILE = RUNTIME / "trace.jsonl"


class TraceLog:

    def __init__(self, capacity=500):
        # Bounded ring: old records are dropped so a long session can't grow
        # memory without limit.
        self.records = deque(maxlen=capacity)
        # Opt-in disk mirror; off by default so normal runs touch no files.
        self.to_file = False

    def record(self, **fields):
        fields["ts"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
        self.records.append(fields)

        if self.to_file:
            try:
                TRACE_FILE.parent.mkdir(parents=True, exist_ok=True)
                with open(TRACE_FILE, "a", encoding="utf-8") as fh:
                    fh.write(json.dumps(fields) + "\n")
            except Exception:
                # Observability must never break the thing it observes.
                pass

    def reset(self):
        self.records.clear()

    def recent(self, n=20):
        return list(self.records)[-n:]
