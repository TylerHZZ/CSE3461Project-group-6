"""Foundation-owned identity, bounded queues and connection lifecycle."""
from __future__ import annotations

import queue
import threading
import time
from dataclasses import dataclass, field
from uuid import uuid4

from . import config
from .features.enhancement import DelayPolicy
from .protocol import AppError, EnqueueResult, WireMessage, DeliveryMeta, valid_username
from .telemetry import EventSink, TelemetryError
from .transport import FramedConnection, encode_frame


@dataclass(frozen=True)
class SessionView:
    session_id: str
    username: str
    peer_address: tuple[str, int]


class Directory:
    """Read-only lookup facade; features never receive the SessionManager."""
    def __init__(self, manager):
        self._manager = manager

    def find(self, username: str) -> SessionView | None:
        with self._manager._lock:
            sid = self._manager._names.get(username)
            return self._manager._view_locked(sid)

    def others(self, origin_session_id: str) -> tuple[SessionView, ...]:
        with self._manager._lock:
            return tuple(SessionView(s.session_id, s.username, s.peer_address)
                         for s in self._manager._sessions.values()
                         if s.state == 'registered' and s.session_id != origin_session_id)


@dataclass
class _Outbound:
    message: WireMessage
    meta: DeliveryMeta | None
    frame_bytes: int
    enqueued_ns: int


@dataclass
class _Session:
    session_id: str
    channel: FramedConnection
    peer_address: tuple[str, int]
    local_address: object
    registration_deadline_ns: int
    outbound: queue.Queue = field(default_factory=lambda: queue.Queue(config.OUTBOUND_CAPACITY))
    username: str | None = None
    state: str = 'awaiting_registration'
    last_request_id: int = 0
    close_deadline_ns: int | None = None
    reason: str | None = None
    reader: threading.Thread | None = None
    writer: threading.Thread | None = None
    cancel_delay: threading.Event = field(default_factory=threading.Event)
    delay_policy: DelayPolicy | None = None


class SessionManager:
    def __init__(self, max_clients: int, events: EventSink, delay_config=None):
        self.max_clients, self.events = max_clients, events
        self.delay_config = delay_config or config.ServerConfig()
        self._lock = threading.Lock()
        self._sessions: dict[str, _Session] = {}
        self._names: dict[str, str] = {}
        self.directory = Directory(self)
        self.discarded = 0

    def _emit(self, name, fields):
        try:
            self.events.emit(name, fields)
        except TelemetryError:
            # The supervisor observes events.failed. Resource cleanup must still run.
            pass

    def attach(self, channel, peer_address, accepted_ns) -> _Session | None:
        record = _Session(str(uuid4()), channel, peer_address, channel.socket.getsockname(),
                          accepted_ns + int(config.REGISTRATION_S*1e9))
        with self._lock:
            if len(self._sessions) >= self.max_clients:
                return None
            self._sessions[record.session_id] = record
        self._emit('connection_opened', dict(session_id=record.session_id, local_address=record.local_address,
                                             peer_address=peer_address))
        return record

    def records(self):
        with self._lock:
            return tuple(self._sessions.values())

    def get(self, session_id):
        with self._lock:
            return self._sessions.get(session_id)

    def _view_locked(self, session_id):
        s = self._sessions.get(session_id)
        return SessionView(s.session_id, s.username, s.peer_address) if s and s.state == 'registered' else None

    def view(self, session_id):
        with self._lock:
            return self._view_locked(session_id)

    def state(self, session_id):
        with self._lock:
            s = self._sessions.get(session_id)
            return s.state if s else 'closed'

    def consume_id(self, session_id, request_id):
        with self._lock:
            s = self._sessions.get(session_id)
            if not s or s.state in ('closing', 'closed') or request_id <= s.last_request_id:
                return False
            s.last_request_id = request_id
            return True

    def _item(self, message, meta):
        return _Outbound(message, meta, len(encode_frame(message)), time.monotonic_ns())

    @staticmethod
    def _put_locked(s, item):
        try:
            item.enqueued_ns = time.monotonic_ns()
            s.outbound.put_nowait(item)
            return EnqueueResult(True)
        except queue.Full:
            return EnqueueResult(False, 'full')

    @staticmethod
    def _fields(session_id, item):
        fields = dict(target_session_id=session_id, frame_type=item.message.type,
                      request_id=item.message.request_id, frame_bytes=item.frame_bytes,
                      enqueued_ns=item.enqueued_ns)
        if item.meta:
            fields.update(message_id=item.meta.message_id, origin_session_id=item.meta.origin_session_id,
                          origin_request_id=item.meta.origin_request_id, feature=item.meta.feature)
        return fields

    def _log_admission(self, session_id, item, result):
        fields = self._fields(session_id, item)
        if not result.queued:
            fields['reason'] = result.reason
        self._emit('outbound_enqueued' if result.queued else 'outbound_not_queued', fields)

    def register(self, session_id, username, registered_reply) -> SessionView | AppError:
        if not valid_username(username):
            return AppError('INVALID_USERNAME', 'Invalid username.')
        if (registered_reply.type != 'registered' or registered_reply.data['username'] != username or
                registered_reply.data['session_id'] != session_id):
            return AppError('INTERNAL_ERROR', 'Invalid registration response.', True)
        item = self._item(registered_reply, None)
        admission = None
        with self._lock:
            s = self._sessions.get(session_id)
            if not s or s.state in ('closing', 'closed'):
                result = AppError('INTERNAL_ERROR', 'Connection is closing.', True)
            elif s.state == 'registered':
                result = AppError('ALREADY_REGISTERED', 'Already registered.')
            elif time.monotonic_ns() >= s.registration_deadline_ns:
                result = AppError('REGISTRATION_TIMEOUT', 'Registration deadline expired.', True)
            elif username in self._names:
                result = AppError('USERNAME_TAKEN', 'Username is already in use.')
            else:
                admission = self._put_locked(s, item)
                if admission.queued:
                    s.username, s.state = username, 'registered'
                    self._names[username] = session_id
                    result = self._view_locked(session_id)
                else:
                    result = AppError('INTERNAL_ERROR', 'Registration response queue is full.', True)
        if admission is not None:
            self._log_admission(session_id, item, admission)
        self._emit('registration_result', dict(session_id=session_id, requested_username=username,
                                               accepted=isinstance(result, SessionView),
                                               error_code=result.code if isinstance(result, AppError) else None))
        return result

    def enqueue(self, session_id, message, meta: DeliveryMeta | None) -> EnqueueResult:
        item = self._item(message, meta)
        with self._lock:
            s = self._sessions.get(session_id)
            result = self._put_locked(s, item) if s and s.state not in ('closing', 'closed') else EnqueueResult(False, 'closed')
        self._log_admission(session_id, item, result)
        return result

    def close(self, session_id, reason, final_message=None, drain=False) -> None:
        item = self._item(final_message, None) if final_message else None
        admission = None
        with self._lock:
            s = self._sessions.get(session_id)
            if not s or s.state == 'closed':
                return
            if s.state == 'closing' and drain:
                return
            if s.username and self._names.get(s.username) == session_id:
                del self._names[s.username]
            s.state, s.reason = 'closing', reason
            s.cancel_delay.set()
            s.close_deadline_ns = time.monotonic_ns() + int(config.DRAIN_S*1e9) if drain else None
            if item:
                admission = self._put_locked(s, item)
                drain = drain and admission.queued
        if admission is not None:
            self._log_admission(session_id, item, admission)
        if not drain:
            self._finish(s)

    def _finish(self, s):
        discarded = []
        with self._lock:
            if s.state == 'closed':
                return
            s.state = 'closed'
            s.cancel_delay.set()
            if s.username and self._names.get(s.username) == s.session_id:
                del self._names[s.username]
            while True:
                try:
                    discarded.append(s.outbound.get_nowait())
                except queue.Empty:
                    break
            self.discarded += len(discarded)
        s.channel.close()
        for item in discarded:
            self._emit('outbound_discarded', dict(self._fields(s.session_id, item), reason='shutdown' if s.reason == 'server_shutdown' else 'closed'))
        self._emit('connection_closed', dict(session_id=s.session_id, local_address=s.local_address,
                                              peer_address=s.peer_address, reason=s.reason))

    def writer_loop(self, s):
        try:
            while True:
                with self._lock:
                    state, deadline = s.state, s.close_deadline_ns
                if state == 'closed':
                    return
                if state == 'closing' and (s.outbound.empty() or (deadline and time.monotonic_ns() >= deadline)):
                    self._finish(s)
                    return
                try:
                    item = s.outbound.get(timeout=.05)
                except queue.Empty:
                    continue
                dequeued = time.monotonic_ns()
                fields = self._fields(s.session_id, item)
                if item.message.type == 'chat_message':
                    if s.delay_policy is None:
                        cfg = self.delay_config
                        s.delay_policy = DelayPolicy(cfg.delay_mode, cfg.delay_ms, cfg.jitter_ms,
                                                     cfg.delay_seed, s.username)
                    self._emit('chat_dequeued', dict(fields, dequeued_ns=dequeued))
                    # The writer owns its RNG; no directory/log lock is held here.
                    observation = s.delay_policy.before_chat_write(s.cancel_delay)
                    self._emit('chat_delay_completed', dict(fields, mode=s.delay_policy.mode,
                        dequeued_ns=dequeued, queue_only_ns=dequeued-item.enqueued_ns,
                        selected_ms=observation.selected_ms, wait_started_ns=observation.started_ns,
                        wait_ended_ns=observation.ended_ns,
                        actual_wait_ns=observation.ended_ns-observation.started_ns,
                        cancelled=observation.cancelled))
                    if observation.cancelled:
                        with self._lock:
                            self.discarded += 1
                        self._emit('outbound_discarded', dict(fields, reason='delay_cancelled'))
                        continue
                started = time.monotonic_ns()
                try:
                    s.channel.write(item.message)
                except OSError as exc:
                    self._emit('frame_write_failed', dict(fields, started_ns=started, ended_ns=time.monotonic_ns(), error_code=type(exc).__name__))
                    self.close(s.session_id, 'write_failed', None, False)
                    return
                self._emit('frame_write_completed', dict(fields, started_ns=started, ended_ns=time.monotonic_ns()))
        except Exception:
            self.close(s.session_id, 'writer_internal_error', None, False)

    def maintain(self):
        for s in self.records():
            with self._lock:
                expired = s.state == 'closing' and s.close_deadline_ns and time.monotonic_ns() >= s.close_deadline_ns
            if expired:
                self.close(s.session_id, 'drain_timeout', None, False)
            with self._lock:
                if s.state == 'closed' and all(t is None or not t.is_alive() for t in (s.reader, s.writer)):
                    self._sessions.pop(s.session_id, None)
