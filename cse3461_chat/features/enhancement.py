"""F3 A: writer-local, cancellable application delay (not network propagation)."""
import hashlib
import random
import threading
import time
from dataclasses import dataclass

from ..protocol import AppError, EmptyEnhancementRequest, RequestContext


@dataclass(frozen=True)
class WaitObservation:
    selected_ms: float
    started_ns: int
    ended_ns: int
    cancelled: bool


class DelayPolicy:
    """Owned by one recipient writer; validated immutable startup parameters."""
    def __init__(self, mode, delay_ms, jitter_ms, seed, username):
        self.mode, self.delay_ms, self.jitter_ms = mode, delay_ms, jitter_ms
        digest = hashlib.sha256(f'{seed}:{username}'.encode('utf-8')).digest()
        self._random = random.Random(int.from_bytes(digest, 'big'))

    def select_ms(self):
        if self.mode == 'off':
            return 0.0
        if self.mode == 'fixed':
            return self.delay_ms
        return self._random.uniform(self.delay_ms-self.jitter_ms, self.delay_ms+self.jitter_ms)

    def before_chat_write(self, cancel: threading.Event) -> WaitObservation:
        selected = self.select_ms()
        started = time.monotonic_ns()
        # Do not call wait(0) on the disabled/zero hot path. Disabled mode keeps
        # the framework's existing graceful-drain behavior.
        cancelled = self.mode != 'off' and cancel.is_set()
        if selected > 0 and not cancelled:
            cancelled = cancel.wait(selected/1000)
        ended = time.monotonic_ns()
        return WaitObservation(selected, started, ended, cancelled)


def handle_enhancement(ctx: RequestContext, request: EmptyEnhancementRequest) -> AppError:
    return AppError('STARTUP_CONFIG_ONLY',
        'F3 A runs transparently on chat writes. Configure delay/jitter at server startup; '
        '/enhance does not start an experiment or change the policy.', feature='f3')
