"""Threaded chat server. Run with python -m cse3461_chat.server."""
import signal
import socket
import sys
import threading
import time

from . import config as limits
from .config import parse_server_args, validate_config
from .dispatch import Dispatcher
from .features import build_handlers
from .protocol import AppError, ProtocolError, make_message
from .sessions import SessionManager
from .telemetry import TelemetryError, open_event_sink, process_metadata
from .transport import FramedConnection, ReadDeadline


class ServerRuntime:
    def __init__(self, output=print):
        self.output = output
        self.ready = threading.Event()
        self._stop = threading.Event()
        self.reason = 'server_shutdown'
        self.address = None
        self.manager = None

    def stop(self, reason: str) -> None:
        self.reason = reason
        self._stop.set()

    def _receiver(self, s, dispatcher):
        try:
            while self.manager.state(s.session_id) not in ('closing','closed'):
                deadline = s.registration_deadline_ns if self.manager.state(s.session_id) == 'awaiting_registration' else None
                envelope = s.channel.receive(deadline)
                if envelope is None:
                    self.manager.close(s.session_id, 'eof', None, False)
                    return
                info = s.channel.last_receive
                self.manager._emit('request_received', dict(session_id=s.session_id,
                    request_id=envelope.request_id, type=envelope.type, received_ns=info.received_ns,
                    payload_bytes=info.payload_bytes))
                dispatcher.handle(s.session_id, envelope, info.received_ns)
        except ReadDeadline:
            dispatcher.reject(s.session_id, AppError('REGISTRATION_TIMEOUT', 'Registration deadline expired.', True))
        except ProtocolError as exc:
            dispatcher.reject(s.session_id, AppError(exc.code, exc.message, True), exc.request_id,
                              drain=exc.code != 'TRUNCATED_FRAME')
        except OSError:
            if self.manager.state(s.session_id) not in ('closing','closed'):
                self.manager.close(s.session_id, 'connection_error', None, False)
        except Exception as exc:
            self.manager._emit('internal_error', dict(session_id=s.session_id, component='receiver', error_type=type(exc).__name__))
            dispatcher.reject(s.session_id, AppError('INTERNAL_ERROR', 'Internal connection error.', True))
        finally:
            if self.manager.state(s.session_id) not in ('closing','closed'):
                self.manager.close(s.session_id, 'receiver_stopped', None, False)

    def _shutdown(self):
        deadline = time.monotonic()+limits.SHUTDOWN_S
        for s in self.manager.records():
            self.manager.close(s.session_id, 'server_shutdown', make_message('bye', None, {'reason':'server_shutdown'}), True)
        while self.manager.records() and time.monotonic() < deadline:
            self.manager.maintain()
            for s in self.manager.records():
                if time.monotonic() >= deadline-.2:
                    self.manager.close(s.session_id, 'shutdown_timeout', None, False)
                for worker in (s.reader, s.writer):
                    if worker and worker is not threading.current_thread():
                        worker.join(max(0, min(.01, deadline-time.monotonic())))
        self.manager.maintain()
        return not self.manager.records()

    def run(self, config, handlers, events) -> int:
        code = 0
        listener = None
        self.manager = SessionManager(config.max_clients, events)
        dispatcher = Dispatcher(self.manager, handlers, events)
        try:
            validate_config(config)
            events.emit('process_started', process_metadata(config, handlers.descriptors))
            listener = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            listener.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            listener.bind((config.host, config.port))
            listener.listen(config.max_clients)
            listener.settimeout(.05)
            self.address = listener.getsockname()
            self.output(f'Listening on {self.address[0]}:{self.address[1]}; '
                        f'F2={"enabled" if dispatcher.capabilities["f2"]["enabled"] else "disabled"}; F1/F3 not implemented.')
            self.ready.set()
            while not self._stop.is_set():
                self.manager.maintain()
                if events.failed.is_set():
                    raise TelemetryError('Requested telemetry failed; evidence is invalid.')
                try:
                    sock, peer = listener.accept()
                except socket.timeout:
                    continue
                accepted_ns = time.monotonic_ns()
                channel = FramedConnection(sock)
                s = self.manager.attach(channel, peer, accepted_ns)
                if s is None:
                    local = sock.getsockname()
                    channel.close()
                    events.emit('connection_rejected', dict(local_address=local, peer_address=peer, reason='capacity'))
                    continue
                hello = make_message('hello', None, dict(session_id=s.session_id, registration_required=True,
                    max_frame_bytes=65536, max_text_bytes=4096, registration_timeout_s=limits.REGISTRATION_S,
                    features=dispatcher.capabilities))
                if not self.manager.enqueue(s.session_id, hello, None).queued:
                    self.manager.close(s.session_id, 'hello_queue_failed', None, False)
                    continue
                s.writer = threading.Thread(target=self.manager.writer_loop, args=(s,), name=f'writer-{s.session_id}')
                s.reader = threading.Thread(target=self._receiver, args=(s,dispatcher), name=f'receiver-{s.session_id}')
                s.writer.start()
                s.reader.start()
        except ValueError as exc:
            code = 2
            self.reason = 'invalid_config'
            print(f'Configuration error: {exc}', file=sys.stderr)
        except (OSError, TelemetryError) as exc:
            code = 1
            self.reason = 'telemetry_failure' if events.failed.is_set() else 'runtime_failure'
            print(f'Server error: {exc}', file=sys.stderr)
        finally:
            if listener is not None:
                listener.close()
            clean = self._shutdown()
            if not clean or not events.valid:
                code = 1
            try:
                events.emit('process_stopped', dict(reason=self.reason, clean=clean, pending_count=0,
                    discarded_count=self.manager.discarded, telemetry_valid=events.valid))
            except TelemetryError:
                code = 1
                print('Telemetry invalid; final evidence record could not be written.', file=sys.stderr)
            try:
                events.close()
            except TelemetryError as exc:
                code = 1
                print(str(exc), file=sys.stderr)
        return code


def main(argv=None):
    config = parse_server_args(argv)
    try:
        events = open_event_sink('server', config.run_id, config.log_file)
    except TelemetryError as exc:
        print(str(exc), file=sys.stderr)
        return 1
    runtime = ServerRuntime()
    for sig in (signal.SIGINT, signal.SIGTERM):
        signal.signal(sig, lambda signum, frame: runtime.stop('server_shutdown'))
    return runtime.run(config, build_handlers(config.features), events)


if __name__ == '__main__':
    sys.exit(main())
