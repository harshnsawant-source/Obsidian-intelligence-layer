# K-C: consent audit log for private-note content that leaves the device.
#
# Every cloud send of vault-derived content MUST be recorded here BEFORE the send
# (see vault_qa.cloud_synthesis), so the log is a complete record of everything
# that has ever left the device. record_consent raises on write failure so the
# caller can FAIL CLOSED (do not send if we cannot log).

import json
import time

from configs.paths import CONSENT_LOG


def record_consent(query, sources, char_count, destination="ollama-cloud-coder"):

    record = {
        "ts": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "query": query,
        "sources": list(sources or []),
        "chars": int(char_count),
        "destination": destination,
    }

    # No try/except: a write failure must propagate so the caller does NOT send.
    CONSENT_LOG.parent.mkdir(parents=True, exist_ok=True)
    with open(CONSENT_LOG, "a", encoding="utf-8") as fh:
        fh.write(json.dumps(record) + "\n")

    return record


def read_consent_log():

    if not CONSENT_LOG.exists():
        return []

    out = []
    for line in CONSENT_LOG.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            out.append(json.loads(line))
        except Exception:
            continue
    return out


def consent_count():
    return len(read_consent_log())
