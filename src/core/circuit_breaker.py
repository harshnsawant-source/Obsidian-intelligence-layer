import time


class CircuitBreaker:

    # Per-provider failure gate. CLOSED -> (fails) -> OPEN -> (cooldown) ->
    # HALF_OPEN -> (probe ok) -> CLOSED. Recovery is lazy: the next request
    # after the cooldown elapses gets one probe, no background thread needed.

    def __init__(self, threshold=3, cooldown=60):
        self.threshold = threshold
        self.cooldown = cooldown
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

    def record_failure(self):
        self.fails += 1
        if self.state == "HALF_OPEN" or self.fails >= self.threshold:
            self.state = "OPEN"
            self.opened_at = time.time()
