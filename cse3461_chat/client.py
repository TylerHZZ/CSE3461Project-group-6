"""Single-controller client with a receiver and a daemon stdin reader."""
from __future__ import annotations

import queue
import socket
import sys
import threading
import time
from collections import deque
from dataclasses import dataclass

from . import config as limits
from .commands import parse_input, LocalUsageError, safe_display, help_text, render_event
from .config import parse_client_args, validate_config
from .protocol import (AppError, ProtocolError, Disconnected, ConnectionInfo, capabilities,
                       make_message, validate_message, valid_id, MAX_REQUEST_ID)
from .telemetry import TelemetryError, open_event_sink, process_metadata
from .transport import FramedConnection


class LocalClientError(ValueError):
    pass


@dataclass(frozen=True)
class _Pending:
    type: str
    sent_ns: int
    username: str | None = None


class ClientRuntime:
    def __init__(self):
        self.state = 'DISCONNECTED'
        self.session_id = None
        self.username = None
        self.features = capabilities()
        self.channel = None
        self.reader = None
        self.events = None
        self.pending: dict[int, _Pending] = {}
        self._next_id = 1
        self._queue = queue.Queue(limits.EVENT_CAPACITY)
        self.terminal = threading.Event()
        self._reason_lock = threading.Lock()
        self._transport_reason = None
        self._notices = deque()
        self._owner = threading.get_ident()
        self._hello_deadline = None
        self._close_deadline = None
        self._stopped = False
        self.close_reason = None
        self.unknown_count = 0

    def _check_owner(self):
        if threading.get_ident() != self._owner:
            raise RuntimeError('ClientRuntime must be used from its controller thread.')

    def _transport_failed(self, reason):
        with self._reason_lock:
            if not self.terminal.is_set():
                self._transport_reason = reason
                self.terminal.set()
        if self.channel:
            self.channel.close()

    def connect(self, config, events) -> ConnectionInfo:
        self._check_owner()
        if self.state != 'DISCONNECTED':
            raise LocalClientError('Use a fresh client instance for a new connection.')
        validate_config(config)
        self.events = events
        events.emit('process_started', process_metadata(config))
        self.state = 'CONNECTING'
        sock = socket.socket(socket.AF_INET,socket.SOCK_STREAM)
        try:
            sock.settimeout(limits.CONNECT_S)
            sock.connect((config.host,config.port))
            self.channel = FramedConnection(sock)
            info = ConnectionInfo(sock.getsockname(),sock.getpeername())
            events.emit('connection_opened',dict(local_address=info.local_address,peer_address=info.server_address))
        except Exception:
            sock.close()
            raise
        self.state = 'AWAITING_HELLO'
        self._hello_deadline = time.monotonic_ns()+int(limits.HELLO_S*1e9)
        self.reader = threading.Thread(target=self._receive,name='client-receiver')
        self.reader.start()
        return info

    def _receive(self):
        try:
            while not self.terminal.is_set():
                envelope = self.channel.receive(None)
                if envelope is None:
                    self._transport_failed('eof')
                    return
                if envelope.v != 1 or (envelope.request_id is not None and not valid_id(envelope.request_id)):
                    raise ProtocolError('INVALID_ENVELOPE')
                message = validate_message(envelope,'s2c')
                if isinstance(message,AppError):
                    raise ProtocolError(message.code)
                try:
                    self._queue.put_nowait((message,self.channel.last_receive.received_ns))
                except queue.Full:
                    self._transport_failed('event_queue_overflow')
                    return
        except ProtocolError as exc:
            self._transport_failed('protocol_error:'+exc.code)
        except OSError:
            self._transport_failed('connection_error')
        except Exception:
            self._transport_failed('receiver_internal_error')

    def send(self, type: str, data: object) -> int:
        self._check_owner()
        allowed = {'AWAITING_REGISTRATION': {'register','disconnect'},
                   'REGISTERED': {'broadcast_send','private_send','enhancement_request','disconnect'}}
        if type not in allowed.get(self.state,set()):
            raise LocalClientError('This request is not allowed in the current connection state.')
        if len(self.pending) >= limits.MAX_PENDING:
            raise LocalClientError('Busy: 32 requests are already pending; input was not sent.')
        if type == 'register' and any(p.type == 'register' for p in self.pending.values()):
            raise LocalClientError('Registration is pending; input was not sent.')
        if self._next_id > MAX_REQUEST_ID:
            raise LocalClientError('Request ID range exhausted; close this connection.')
        rid = self._next_id
        try:
            message = make_message(type,rid,data)
        except ValueError as exc:
            raise LocalClientError(str(exc)) from exc
        self._next_id += 1
        sent_ns = time.monotonic_ns()
        self.pending[rid] = _Pending(type,sent_ns,data.get('username') if type == 'register' else None)
        try:
            self.channel.write(message)
            self.events.emit('client_request_sent',dict(request_id=rid,type=type,occurred_ns=sent_ns))
        except OSError:
            self._transport_failed('write_failed')
            raise
        if type == 'disconnect':
            self.state = 'CLOSING'
            self._close_deadline = time.monotonic_ns()+int(limits.DRAIN_S*1e9)
        return rid

    def _unknown(self, rid):
        self.pending.pop(rid,None)
        self.unknown_count += 1
        self._notices.append(f'Request {rid}: outcome unknown; not resent.')

    def drain_notices(self):
        self._check_owner()
        result = tuple(self._notices)
        self._notices.clear()
        return result

    def _disconnect(self, reason):
        self.close(reason)
        return Disconnected(reason)

    def next_event(self, timeout_s: float):
        self._check_owner()
        if self.state == 'CLOSED':
            return None
        if self.events.failed.is_set():
            return self._disconnect('telemetry_failure')
        until = time.monotonic()+max(0,timeout_s)
        while True:
            now = time.monotonic_ns()
            if self.state == 'AWAITING_HELLO' and now >= self._hello_deadline:
                return self._disconnect('hello_timeout')
            if self.state == 'CLOSING' and now >= self._close_deadline:
                return self._disconnect('quit_timeout')
            for rid,p in tuple(self.pending.items()):
                if now-p.sent_ns >= int(limits.REQUEST_S*1e9):
                    self._unknown(rid)
                    if p.type == 'register':
                        return self._disconnect('registration_reply_timeout')
            # Fatal protocol/overflow signals bypass a full queue. Orderly EOF drains
            # already validated replies first so a received bye is not hidden.
            if self.terminal.is_set() and self._transport_reason != 'eof':
                return self._disconnect(self._transport_reason)
            try:
                message,occurred_ns = self._queue.get_nowait()
                break
            except queue.Empty:
                if self.terminal.is_set():
                    return self._disconnect(self._transport_reason)
                remaining = until-time.monotonic()
                if remaining <= 0:
                    return None
                self.terminal.wait(min(.01,remaining))
        try:
            self.events.emit('client_response_received',dict(request_id=message.request_id,type=message.type,
                              occurred_ns=occurred_ns,message_id=message.data.get('message_id')))
            result = self._apply(message)
            if message.type == 'chat_message':
                self.events.emit('chat_received', dict(message_id=message.data['message_id'],
                    receiver_session_id=self.session_id, sender=message.data['sender'],
                    mode=message.data['mode'], text_bytes=len(message.data['text'].encode('utf-8')),
                    received_ns=occurred_ns))
            return result
        except TelemetryError:
            return self._disconnect('telemetry_failure')
        except ProtocolError as exc:
            return self._disconnect('protocol_error:'+exc.code)

    def _apply(self, message):
        kind,rid,d = message.type,message.request_id,message.data
        if kind == 'hello':
            if self.state != 'AWAITING_HELLO':
                raise ProtocolError('UNEXPECTED_HELLO')
            self.session_id,self.features = d['session_id'],d['features']
            self.state = 'AWAITING_REGISTRATION'
            return message
        if self.state == 'AWAITING_HELLO':
            raise ProtocolError('HELLO_REQUIRED')
        pending = self.pending.get(rid)
        if kind == 'registered':
            if (self.state not in ('AWAITING_REGISTRATION','CLOSING') or not pending or pending.type != 'register' or
                    pending.username != d['username'] or self.session_id != d['session_id'] or self.features != d['features']):
                raise ProtocolError('REGISTRATION_CORRELATION')
            self.pending.pop(rid)
            self.username = d['username']
            if self.state != 'CLOSING':
                self.state = 'REGISTERED'
        elif kind == 'chat_message':
            if self.state not in ('REGISTERED','CLOSING'):
                raise ProtocolError('NOT_REGISTERED')
        elif kind in ('error','send_result','bye'):
            if pending:
                if kind == 'send_result' and pending.type not in ('broadcast_send','private_send'):
                    raise ProtocolError('RESPONSE_CORRELATION')
                if kind == 'bye' and pending.type != 'disconnect':
                    raise ProtocolError('RESPONSE_CORRELATION')
                self.pending.pop(rid)
            elif rid is not None:
                self._notices.append(f'Late/unmatched response {rid}; completed request state is unchanged.')
            if kind == 'bye':
                if rid is None or pending:
                    self.close(d['reason'])
            elif kind == 'error' and d['fatal']:
                self.close(d['code'])
        return message

    def close(self, reason: str) -> None:
        self._check_owner()
        if self._stopped:
            return
        self._stopped = True
        self.close_reason = reason
        for rid in tuple(self.pending):
            self._unknown(rid)
        self._transport_failed(reason)
        if self.reader:
            self.reader.join(limits.SHUTDOWN_S)
        self.state = 'CLOSED'
        if self.events:
            try:
                self.events.emit('connection_closed',dict(session_id=self.session_id,reason=reason))
                self.events.emit('process_stopped',dict(reason=reason,clean=not (self.reader and self.reader.is_alive()),
                    pending_count=0,unknown_count=self.unknown_count,discarded_count=self._queue.qsize(),telemetry_valid=self.events.valid))
            except TelemetryError:
                print('Telemetry invalid; final evidence record could not be written.',file=sys.stderr)
            try:
                self.events.close()
            except TelemetryError as exc:
                print(str(exc),file=sys.stderr)


def _stdin_worker(commands, stop):
    while not stop.is_set():
        line = sys.stdin.readline()
        value = None if line == '' else line.rstrip('\r\n')
        while not stop.is_set():
            try:
                commands.put(value,timeout=.05)
                break
            except queue.Full:
                continue
        if value is None:
            return


def main(argv=None):
    config = parse_client_args(argv)
    try:
        events = open_event_sink('client',config.run_id,config.log_file)
    except TelemetryError as exc:
        print(str(exc),file=sys.stderr)
        return 1
    client = ClientRuntime()
    input_stop = threading.Event()
    commands = queue.Queue(limits.COMMAND_CAPACITY)
    code,user_quit = 0,False
    try:
        info = client.connect(config,events)
        print(f'Connected: local={info.local_address[0]}:{info.local_address[1]} server={info.server_address[0]}:{info.server_address[1]}',flush=True)
        threading.Thread(target=_stdin_worker,args=(commands,input_stop),name='terminal-input',daemon=True).start()
        while client.state != 'CLOSED':
            event = client.next_event(.05)
            if isinstance(event,Disconnected):
                print('[disconnected] '+safe_display(event.reason),flush=True)
                code = 0 if user_quit else 1
            elif event:
                print(render_event(event),flush=True)
                if event.type == 'hello':
                    if config.username:
                        client.send('register',{'username':config.username})
                    else:
                        print('Username:',flush=True)
                elif event.type == 'error':
                    if event.data['fatal']:
                        code = 1
                    elif client.state == 'AWAITING_REGISTRATION':
                        print('Username (retry):',flush=True)
            for notice in client.drain_notices():
                print(notice,flush=True)
            if client.state in ('CLOSING','CLOSED'):
                continue
            try:
                line = commands.get_nowait()
            except queue.Empty:
                continue
            try:
                if line is None or line == '/quit':
                    user_quit = True
                    if client.state == 'AWAITING_HELLO' or len(client.pending) >= limits.MAX_PENDING:
                        # Closing is always possible, even before protocol readiness
                        # or when no pending-request slot is available for bye.
                        client.close('client_request')
                    else:
                        client.send('disconnect',{})
                elif line == '/help':
                    print(help_text(client.features),flush=True)
                elif client.state == 'AWAITING_REGISTRATION':
                    client.send('register',{'username':line})
                else:
                    command = parse_input(line)
                    if isinstance(command,LocalUsageError):
                        print('[usage] '+command.message,flush=True)
                    else:
                        rid = client.send(command.type,command.data)
                        print(f'[submitted] request={rid}; pending, not delivered.',flush=True)
            except LocalClientError as exc:
                print('[local] '+safe_display(exc),flush=True)
    except KeyboardInterrupt:
        user_quit = True
    except (OSError,ValueError) as exc:
        code = 1
        print('Client error: '+safe_display(exc),file=sys.stderr)
    finally:
        input_stop.set()
        client.close('client_request' if user_quit else 'runtime_failure')
        for notice in client.drain_notices():
            print(notice,flush=True)
        if not events.valid:
            code = 1
    return code


if __name__ == '__main__':
    sys.exit(main())
