"""Bounded TCP framing; reads and writes each have exactly one owner."""
import json
import select
import socket
import struct
import threading
import time
from dataclasses import dataclass

from .protocol import (Envelope, WireMessage, ProtocolError, AppError, CLIENT_TYPES,
                       MAX_FRAME_BYTES, decode_payload, validate_message, valid_id, thaw)

SOCKET_TIMEOUT_S = 1.0
PARTIAL_FRAME_S = 5.0


class ReadDeadline(TimeoutError):
    pass


@dataclass(frozen=True)
class ReceiveInfo:
    payload_bytes: int
    received_ns: int


def encode_frame(message: WireMessage) -> bytes:
    direction = 'c2s' if message.type in CLIENT_TYPES else 's2c'
    if (message.v != 1 or type(message.v) is not int or
            (message.request_id is not None and not valid_id(message.request_id)) or
            (direction == 'c2s' and not valid_id(message.request_id))):
        raise ProtocolError('INVALID_ENVELOPE', 'Invalid outbound envelope.')
    checked = validate_message(message, direction)
    if isinstance(checked, AppError):
        raise ProtocolError(checked.code, checked.message)
    try:
        payload = json.dumps(dict(v=message.v, type=message.type, request_id=message.request_id,
                                  data=thaw(message.data)), ensure_ascii=False,
                             allow_nan=False, separators=(',', ':')).encode('utf-8')
    except (ValueError, UnicodeError, RecursionError) as exc:
        raise ProtocolError('INVALID_JSON') from exc
    if not 1 <= len(payload) <= MAX_FRAME_BYTES:
        raise ProtocolError('FRAME_TOO_LARGE')
    return struct.pack('!I', len(payload)) + payload


class FramedConnection:
    def __init__(self, sock: socket.socket):
        self.socket = sock
        sock.settimeout(SOCKET_TIMEOUT_S)
        self._closed = threading.Event()
        self._close_lock = threading.Lock()
        self.last_receive: ReceiveInfo | None = None

    def receive(self, deadline_ns: int | None) -> Envelope | None:
        frame = bytearray()
        wanted = 4
        size = None
        started_ns = None
        while len(frame) < wanted:
            if self._closed.is_set():
                raise OSError('Connection closed.')
            now = time.monotonic_ns()
            if deadline_ns is not None and now >= deadline_ns:
                raise ReadDeadline('Read deadline expired.')
            partial_deadline = None if started_ns is None else started_ns + int(PARTIAL_FRAME_S*1e9)
            if partial_deadline is not None and now >= partial_deadline:
                raise ProtocolError('FRAME_TIMEOUT')
            deadlines = [d for d in (deadline_ns, partial_deadline) if d is not None]
            wait = min(SOCKET_TIMEOUT_S, max(0, (min(deadlines)-now)/1e9)) if deadlines else SOCKET_TIMEOUT_S
            try:
                readable, _, _ = select.select([self.socket], [], [], wait)
                if not readable:
                    continue
                chunk = self.socket.recv(wanted-len(frame))
            except socket.timeout:
                continue
            except ValueError as exc:
                raise OSError('Connection closed.') from exc
            if not chunk:
                if not frame:
                    return None
                raise ProtocolError('TRUNCATED_FRAME')
            if started_ns is None:
                started_ns = time.monotonic_ns()
            frame.extend(chunk)
            if size is None and len(frame) == 4:
                size = struct.unpack('!I', frame)[0]
                if size == 0:
                    raise ProtocolError('BAD_FRAME')
                if size > MAX_FRAME_BYTES:
                    raise ProtocolError('FRAME_TOO_LARGE')
                wanted = 4 + size
        self.last_receive = ReceiveInfo(size, time.monotonic_ns())
        result = decode_payload(bytes(frame[4:]))
        if isinstance(result, ProtocolError):
            raise result
        return result

    def write(self, message: WireMessage) -> None:
        if self._closed.is_set():
            raise OSError('Connection closed.')
        frame = encode_frame(message)
        try:
            self.socket.sendall(frame)
        except OSError:
            self.close()
            raise

    def close(self) -> None:
        with self._close_lock:
            if self._closed.is_set():
                return
            self._closed.set()
            try:
                self.socket.shutdown(socket.SHUT_RDWR)
            except OSError:
                pass
            self.socket.close()
