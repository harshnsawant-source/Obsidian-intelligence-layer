import sys
import tempfile
import shutil
from pathlib import Path

import core.vault_qa as vq
import core.consent as consent

PASS = []
FAIL = []


def check(name, cond):
    (PASS if cond else FAIL).append(name)
    print(("PASS" if cond else "FAIL"), "-", name)


P = [
    {"source": "/v/docs/a.md", "folder": "docs", "score": 0.62, "snippet": "note A content"},
    {"source": "/v/memories/b.md", "folder": "memories", "score": 0.51, "snippet": "note B content"},
]

_real_q = vq.query_llm
_real_record = vq.record_consent
_real_log = consent.CONSENT_LOG

tmp = Path(tempfile.mkdtemp(prefix="oil_consent_"))
consent.CONSENT_LOG = tmp / "consent_log.jsonl"

try:
    # --- extractive: no LLM call, cites sources --------------------------
    calls = {"n": 0}
    vq.query_llm = lambda prompt, *a, **k: calls.__setitem__("n", calls["n"] + 1) or "X"
    ext = vq.extractive_answer(P)
    check("extractive: makes NO LLM call", calls["n"] == 0)
    check("extractive: cites sources", "a.md" in ext and "b.md" in ext)
    check("extractive: empty passages handled",
          "No matching" in vq.extractive_answer([]))

    # --- local synthesis: sensitive=True (leak guard), not cloud ---------
    captured = {}

    def cap_q(prompt, *a, **k):
        captured.clear()
        captured.update(k)
        return "Local answer grounded in /v/docs/a.md"

    vq.query_llm = cap_q
    text, ok = vq.local_synthesis("q", P)
    check("local: ok answer returned", ok is True and bool(text))
    check("local: sensitive=True (router pins LOCAL)", captured.get("sensitive") is True)
    check("local: prefer_cloud NOT set (cannot reach cloud)",
          not captured.get("prefer_cloud"))

    # --- local degenerate -> ok False (extractive fallback) --------------
    vq.query_llm = lambda prompt, *a, **k: "[NO FINAL ANSWER GENERATED]\n\nThinking..."
    t2, ok2 = vq.local_synthesis("q", P)
    check("local: degenerate -> ok False, fallback to extractive",
          ok2 is False and t2 is None)

    # --- cloud synthesis: logs BEFORE send; prefer_cloud; non-sensitive --
    order = []
    cloud_kw = {}

    def tracking_record(*a, **k):
        order.append("log")
        return _real_record(*a, **k)

    def cloud_q(prompt, *a, **k):
        order.append("send")
        cloud_kw.clear()
        cloud_kw.update(k)
        return "Cloud answer"

    vq.record_consent = tracking_record
    vq.query_llm = cloud_q
    ans = vq.cloud_synthesis("what is X?", P)
    check("cloud: returns an answer", ans == "Cloud answer")
    check("cloud: consent LOGGED before send", order == ["log", "send"])
    check("cloud: uses prefer_cloud=True", cloud_kw.get("prefer_cloud") is True)
    check("cloud: NOT sensitive", not cloud_kw.get("sensitive"))

    logged = consent.read_consent_log()
    check("consent log: one record written", len(logged) == 1)
    check("consent log: record shape", logged[0]["query"] == "what is X?"
          and logged[0]["sources"] == ["/v/docs/a.md", "/v/memories/b.md"]
          and logged[0]["chars"] > 0
          and logged[0]["destination"] == "ollama-cloud-coder")

    # --- fail-closed: if consent logging fails, NOTHING is sent ----------
    sent = {"n": 0}

    def boom(*a, **k):
        raise IOError("disk full")

    vq.record_consent = boom
    vq.query_llm = lambda *a, **k: sent.__setitem__("n", sent["n"] + 1) or "leaked!"
    raised = False
    try:
        vq.cloud_synthesis("q", P)
    except IOError:
        raised = True
    check("cloud: FAIL-CLOSED (no send when consent log fails)",
          raised is True and sent["n"] == 0)

    # --- leak-rate audit (summary) ---------------------------------------
    # Across extractive + local, zero cloud-tier behaviour:
    #   - extractive: 0 LLM calls (above)
    #   - local: sensitive=True every time (above) -> router cannot route cloud
    # Across cloud: #sends == #consent records (1 logged, 1 sent above; the
    # fail-closed case logged 0 and sent 0).
    check("leak audit: cloud sends are 1:1 with consent records",
          len(consent.read_consent_log()) == 1 and order.count("send") == 1)

finally:
    vq.query_llm = _real_q
    vq.record_consent = _real_record
    consent.CONSENT_LOG = _real_log
    shutil.rmtree(tmp, ignore_errors=True)


print(f"\n{len(PASS)} passed, {len(FAIL)} failed")
sys.exit(1 if FAIL else 0)
