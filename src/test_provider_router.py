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


print(f"\n{len(PASS)} passed, {len(FAIL)} failed")
sys.exit(1 if FAIL else 0)
