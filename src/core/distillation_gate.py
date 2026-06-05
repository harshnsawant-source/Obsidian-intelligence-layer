from contextlib import contextmanager


# Process-level switch for the knowledge-distillation learning loop.
#
# Default ENABLED (production behaviour unchanged). The benchmark wraps its run
# in distillation_suppressed() so that, for the duration of the run, no trial
# distils into the (isolated) vault. Because distillation is the ONLY writer to
# the knowledge vault on a benchmark path, suppressing it keeps the isolated
# vault empty — which in turn guarantees no trial can retrieve another trial's
# artifacts (retrieval reads only the vault index).
#
# This module imports nothing, so it is safe to import from anywhere (no cycles).

_enabled = True


def distillation_enabled():
    return _enabled


@contextmanager
def distillation_suppressed():
    global _enabled
    prev = _enabled
    _enabled = False
    try:
        yield
    finally:
        _enabled = prev
