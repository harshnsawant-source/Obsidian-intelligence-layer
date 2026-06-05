import sys

from core.providers.registry import ManagedProvider
from core.router import ProviderRouter, CANNED_FALLBACK
from core.complexity import score_complexity, classify, LOW, HIGH
from core.circuit_breaker import CircuitBreaker

PASS = []
FAIL = []


def check(name, cond):
    (PASS if cond else FAIL).append(name)
    print(("PASS" if cond else "FAIL"), "-", name)


class Fake:
    def __init__(self, name, tier, local, mode="ok"):
        self.name = name
        self.tier = tier
        self.local = local
        self.cost = 0.0
        self.mode = mode
        self.calls = 0

    def generate(self, prompt, fmt=None, max_tokens=8000):
        self.calls += 1
        if self.mode == "fail":
            raise RuntimeError("down")
        return f"OUT[{self.name}]"


def mk(name, tier, local, mode="ok"):
    return ManagedProvider(Fake(name, tier, local, mode))


TRIVIAL = "hi there"
COMPLEX = ("Design and architect a multi-step plan to debug and refactor "
           "this system; explain the trade-offs.")

# --- complexity scoring ---
check("complexity: trivial -> LOW", classify(score_complexity(TRIVIAL)) == LOW)
check("complexity: complex -> HIGH", classify(score_complexity(COMPLEX)) == HIGH)

# --- routing by complexity ---
cloud, local = mk("cloud", 1, False), mk("local", 4, True)
check("route: complex -> cloud first",
      ProviderRouter([cloud, local]).generate(COMPLEX) == "OUT[cloud]")

cloud2, local2 = mk("cloud", 1, False), mk("local", 4, True)
check("route: trivial -> local first (preserve cloud quota)",
      ProviderRouter([cloud2, local2]).generate(TRIVIAL) == "OUT[local]")

# --- prefer_cloud: low-complexity opts into cloud-first, local still floor ---
cloudP, localP = mk("cloud", 1, False), mk("local", 4, True)
check("prefer_cloud: trivial routes cloud-first",
      ProviderRouter([cloudP, localP]).generate(TRIVIAL, prefer_cloud=True) == "OUT[cloud]")

cfp, lop = mk("cloud", 1, False, mode="fail"), mk("local", 4, True)
check("prefer_cloud: still falls over to local floor",
      ProviderRouter([cfp, lop]).generate(TRIVIAL, prefer_cloud=True) == "OUT[local]"
      and cfp.provider.calls == 1)

# privacy outranks prefer_cloud: a sensitive call stays local, cloud untouched
cps, lps = mk("cloud", 1, False), mk("local", 4, True)
out = ProviderRouter([cps, lps]).generate(TRIVIAL, prefer_cloud=True, sensitive=True)
check("prefer_cloud: sensitive still pins local (privacy wins)",
      out == "OUT[local]" and cps.provider.calls == 0)

# --- privacy: sensitive stays local even when complex ---
cloud3, local3 = mk("cloud", 1, False), mk("local", 4, True)
out = ProviderRouter([cloud3, local3]).generate(COMPLEX, sensitive=True)
check("sensitive: stays local, cloud untouched",
      out == "OUT[local]" and cloud3.provider.calls == 0)

# --- failover: cloud down -> local floor ---
cf, lo = mk("cloud", 1, False, mode="fail"), mk("local", 4, True)
out = ProviderRouter([cf, lo]).generate(COMPLEX)
check("failover: cloud down -> local", out == "OUT[local]" and cf.provider.calls == 1)

# --- everything down -> canned (never raises) ---
allfail = ProviderRouter([mk("cloud", 1, False, "fail"), mk("local", 4, True, "fail")])
check("all down -> canned fallback", allfail.generate(COMPLEX) == CANNED_FALLBACK)

# --- circuit breaker lifecycle ---
cb = CircuitBreaker(threshold=2, cooldown=60)
cb.record_failure(); cb.record_failure()
check("breaker: opens after threshold", cb.state == "OPEN" and cb.allow() is False)
cb.opened_at -= 100  # simulate cooldown elapsed
check("breaker: half-open probe after cooldown",
      cb.allow() is True and cb.state == "HALF_OPEN")
cb.record_success()
check("breaker: closes on success", cb.state == "CLOSED")

# --- breaker integration: open provider is skipped ---
cf3, lo3 = mk("cloud", 1, False, mode="fail"), mk("local", 4, True)
r = ProviderRouter([cf3, lo3])
for _ in range(3):           # default threshold 3 -> trip cloud breaker
    r.generate(COMPLEX)
before = cf3.provider.calls
r.generate(COMPLEX)
check("breaker: open provider skipped on next call", cf3.provider.calls == before)

# --- CU3: severe (timeout) failures trip the breaker fast --------------------
sb = CircuitBreaker(threshold=3, cooldown=60)
sb.record_failure(severe=True)
check("CU3: single severe failure opens breaker", sb.state == "OPEN")

nb = CircuitBreaker(threshold=3, cooldown=60)
nb.record_failure(); nb.record_failure()
check("CU3: two normal failures stay closed (threshold 3)", nb.state == "CLOSED")
nb.record_failure()
check("CU3: third normal failure opens", nb.state == "OPEN")


class _ReadTimeout(Exception):
    pass


class _Timeouter:
    def __init__(self, name, tier, local):
        self.name = name
        self.tier = tier
        self.local = local
        self.cost = 0.0
        self.calls = 0

    def generate(self, prompt, fmt=None, max_tokens=8000):
        self.calls += 1
        raise _ReadTimeout("read timed out")


# A local timeout should shed local after ONE failure, not three.
to = ManagedProvider(_Timeouter("local", 4, True))
rto = ProviderRouter([to])
rto.generate(TRIVIAL)                 # one timeout -> severe -> breaker opens
calls_after_first = to.provider.calls
rto.generate(TRIVIAL)                 # breaker open -> provider skipped
check("CU3: timeout sheds provider after one failure",
      calls_after_first == 1 and to.provider.calls == 1)
fail_rec = [r for r in rto.trace.recent(10) if r.get("event") == "provider_failure"][-1]
check("CU3: timeout flagged severe in trace", fail_rec.get("severe") is True)


# --- CU4: expects_code cloud-pins non-sensitive code tasks -------------------
# A low-complexity code task would normally go local-first; expects_code pins cloud.
cc, lc = mk("cloud", 1, False), mk("local", 4, True)
check("CU4: code task routes cloud-first",
      ProviderRouter([cc, lc]).generate(TRIVIAL, expects_code=True) == "OUT[cloud]")

# Local stays the failover floor when cloud is down.
ccf, lcf = mk("cloud", 1, False, mode="fail"), mk("local", 4, True)
check("CU4: code task still falls over to local floor",
      ProviderRouter([ccf, lcf]).generate(TRIVIAL, expects_code=True) == "OUT[local]")

# Privacy outranks the code pin: sensitive code stays local, cloud untouched.
ccs, lcs = mk("cloud", 1, False), mk("local", 4, True)
out = ProviderRouter([ccs, lcs]).generate(TRIVIAL, expects_code=True, sensitive=True)
check("CU4: sensitive code still pins local (privacy wins)",
      out == "OUT[local]" and ccs.provider.calls == 0)

# expects_code is recorded in the trace for observability.
cct, lct = mk("cloud", 1, False), mk("local", 4, True)
rct = ProviderRouter([cct, lct])
rct.generate(TRIVIAL, expects_code=True)
check("CU4: expects_code recorded in trace",
      rct.trace.recent(1)[0].get("expects_code") is True)


# --- CU8: per-call tracing (additive; must not change returned values) ------

# success path: one record, served_by set, no fallback
ct, lt = mk("cloud", 1, False), mk("local", 4, True)
rt = ProviderRouter([ct, lt])
out = rt.generate(COMPLEX)
rec = rt.trace.recent(1)[0]
check("trace: success records served_by", rec["served_by"] == "cloud")
check("trace: success ok flag", rec["ok"] is True and rec["output_kind"] == "ok")
check("trace: no fallback when first provider serves", rec["fallback_used"] is False)
check("trace: return value unchanged by tracing", out == "OUT[cloud]")

# failover path: cloud fails -> local serves, fallback_used True, both tried
cft, lft = mk("cloud", 1, False, mode="fail"), mk("local", 4, True)
rt2 = ProviderRouter([cft, lft])
rt2.generate(COMPLEX)
rec2 = rt2.trace.recent(1)[0]
check("trace: fallback served_by is local", rec2["served_by"] == "local")
check("trace: fallback_used flagged", rec2["fallback_used"] is True)
check("trace: providers_tried lists both", rec2["providers_tried"] == ["cloud", "local"])

# all-down path: failure record then a canned generate record
allf = ProviderRouter([mk("cloud", 1, False, "fail"), mk("local", 4, True, "fail")])
allf.generate(COMPLEX)
recs = allf.trace.recent(10)
check("trace: provider_failure events recorded",
      sum(1 for r in recs if r.get("event") == "provider_failure") == 2)
final = [r for r in recs if r.get("event") == "generate"][-1]
check("trace: all-down records canned outcome",
      final["ok"] is False and final["output_kind"] == "canned" and final["served_by"] is None)

# ring is bounded
small = ProviderRouter([mk("cloud", 1, False)])
small.trace.records = type(small.trace.records)(maxlen=3)
for _ in range(5):
    small.generate(COMPLEX)
check("trace: ring bounded to capacity", len(small.trace.records) == 3)


# --- CU1: per-provider timeout configuration -------------------------------
import core.providers.base as base_mod
from core.providers.base import OllamaProvider, Provider
from core.providers.registry import build_registry


class _FakeResp:
    def raise_for_status(self):
        pass

    def json(self):
        return {"response": "ok"}


class _CapturingRequests:
    def __init__(self):
        self.last_timeout = None

    def post(self, url, json=None, timeout=None):
        self.last_timeout = timeout
        return _FakeResp()


# OllamaProvider passes its configured timeout through to requests.post.
_saved_requests = base_mod.requests
cap = _CapturingRequests()
base_mod.requests = cap
try:
    OllamaProvider("p", "m", timeout=42).generate("hi")
    check("CU1: provider passes configured timeout to request",
          cap.last_timeout == 42)

    # Default timeout applies when none configured (no more hardcoded 600).
    OllamaProvider("p", "m").generate("hi")
    check("CU1: default timeout used when unset",
          cap.last_timeout == Provider.DEFAULT_TIMEOUT)
finally:
    base_mod.requests = _saved_requests

# Registry wires the per-provider timeouts from configs/providers.py.
reg = {m.name: m.provider.timeout for m in build_registry()}
check("CU1: cloud timeout wired from config (300)",
      reg.get("ollama-cloud-coder") == 300)
check("CU1: local timeout wired from config (120, bounded)",
      reg.get("ollama-local") == 120)


# --- CU2: local generation token cap ---------------------------------------
class _CapturingPayload:
    def __init__(self):
        self.last_num_predict = None

    def post(self, url, json=None, timeout=None):
        self.last_num_predict = json["options"]["num_predict"]
        return _FakeResp()


_saved_requests = base_mod.requests
capp = _CapturingPayload()
base_mod.requests = capp
try:
    # Capped provider clamps a large request down to the cap.
    OllamaProvider("local", "m", max_tokens_cap=1500).generate("hi", max_tokens=8000)
    check("CU2: large request clamped to cap", capp.last_num_predict == 1500)

    # A request already under the cap is left untouched.
    OllamaProvider("local", "m", max_tokens_cap=1500).generate("hi", max_tokens=500)
    check("CU2: request under cap unchanged", capp.last_num_predict == 500)

    # Uncapped provider passes the request through verbatim.
    OllamaProvider("cloud", "m").generate("hi", max_tokens=8000)
    check("CU2: uncapped provider passes tokens through", capp.last_num_predict == 8000)
finally:
    base_mod.requests = _saved_requests

# Registry wires the cap: local bounded, cloud uncapped.
caps = {m.name: m.provider.max_tokens_cap for m in build_registry()}
check("CU2: local token cap wired from config (1500)",
      caps.get("ollama-local") == 1500)
check("CU2: cloud left uncapped", caps.get("ollama-cloud-coder") is None)


print(f"\n{len(PASS)} passed, {len(FAIL)} failed")
sys.exit(1 if FAIL else 0)
