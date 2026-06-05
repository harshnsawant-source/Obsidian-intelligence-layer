import time


class CircuitBreaker:

    # Per-provider failure gate. CLOSED -> (fails) -> OPEN -> (cooldown) ->
    # HALF_OPEN -> (probe ok) -> CLOSED. Recovery is lazy: the next request
    # after the cooldown elapses gets one probe, no background thread needed.

    def __init__(self, threshold=3, cooldown=60, severe_threshold=1):
        self.threshold = threshold
        self.cooldown = cooldown
        # A "severe" failure (e.g. a request timeout — expensive to repeat) trips
        # the breaker after far fewer occurrences than a normal error, so we stop
        # paying the timeout cost over and over before shedding the provider.
        self.severe_threshold = severe_threshold
        self.fails = 0
        self.state = "CLOSED"
        self.opened_at = 0.0

    def allow(self):
        if self.state == "OPEN":
            if time.time() - self.opened_at >= self.cooldown:
                self.state = "HALF_OPEN"
                return True
            return False
        return True

    def record_success(self):
        self.fails = 0
        self.state = "CLOSED"

    def _open(self):
        self.state = "OPEN"
        self.opened_at = time.time()

    def record_failure(self, severe=False):
        self.fails += 1
        limit = self.severe_threshold if severe else self.threshold
        if self.state == "HALF_OPEN" or self.fails >= limit:
            self._open()
