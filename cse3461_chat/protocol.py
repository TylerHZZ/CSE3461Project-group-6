"""Protocol v1 contracts. No network, registry or feature execution lives here."""
from __future__ import annotations

import json
import math
import re
import unicodedata
from dataclasses import dataclass
from types import MappingProxyType
from typing import TYPE_CHECKING, Mapping
from uuid import UUID

if TYPE_CHECKING:
    from .sessions import Directory, SessionView

MAX_FRAME_BYTES = 65536
MAX_TEXT_BYTES = 4096
MAX_REQUEST_ID = 9007199254740991
CLIENT_TYPES = frozenset({'register', 'broadcast_send', 'private_send', 'enhancement_request', 'disconnect'})
SERVER_TYPES = frozenset({'hello', 'registered', 'chat_message', 'send_result', 'bye', 'error'})
FEATURE_TYPES = MappingProxyType({'broadcast_send': 'f1', 'private_send': 'f2', 'enhancement_request': 'f3'})


def freeze(value):
    if isinstance(value, Mapping):
        return MappingProxyType({k: freeze(v) for k, v in value.items()})
    if isinstance(value, (list, tuple)):
        return tuple(freeze(v) for v in value)
    return value


def thaw(value):
    if isinstance(value, Mapping):
        return {k: thaw(v) for k, v in value.items()}
    if isinstance(value, tuple):
        return [thaw(v) for v in value]
    return value


@dataclass(frozen=True)
class Envelope:
    v: int
    type: str
    request_id: int | None
    data: Mapping


@dataclass(frozen=True)
class WireMessage(Envelope):
    def __post_init__(self):
        object.__setattr__(self, 'data', freeze(self.data))


class ProtocolError(Exception):
    def __init__(self, code: str, message: str = 'Invalid protocol input.', request_id: int | None = None):
        super().__init__(message)
        self.code, self.message, self.request_id = code, message, request_id


@dataclass(frozen=True)
class AppError:
    code: str
    message: str
    fatal: bool = False
    feature: str | None = None


@dataclass(frozen=True)
class BroadcastRequest:
    text: str


@dataclass(frozen=True)
class PrivateRequest:
    to: str
    text: str


@dataclass(frozen=True)
class EmptyEnhancementRequest:
    pass


@dataclass(frozen=True)
class RequestContext:
    sender: SessionView
    request_id: int
    received_ns: int
    directory: Directory


@dataclass(frozen=True)
class RoutePlan:
    recipients: tuple[SessionView, ...]

    def __post_init__(self):
        if not isinstance(self.recipients, tuple) or not self.recipients:
            raise ValueError('A route must contain a nonempty tuple of recipients.')
        if len({v.session_id for v in self.recipients}) != len(self.recipients):
            raise ValueError('Duplicate recipient session.')


FeatureOutcome = RoutePlan | AppError


@dataclass(frozen=True)
class EnqueueResult:
    queued: bool
    reason: str | None = None


@dataclass(frozen=True)
class DeliveryMeta:
    message_id: str
    origin_session_id: str
    origin_request_id: int
    feature: str
    target_session_id: str
    enqueued_ns: int


@dataclass(frozen=True)
class PublishResult:
    message_id: str
    status: str
    selected_count: int
    queued_count: int
    not_queued_count: int


@dataclass(frozen=True)
class ConnectionInfo:
    local_address: tuple[str, int]
    server_address: tuple[str, int]


@dataclass(frozen=True)
class Disconnected:
    reason: str


ClientEvent = WireMessage | Disconnected


@dataclass(frozen=True)
class FeatureDescriptor:
    id: str
    implemented: bool = False
    enabled: bool = False
    variant: str | None = None


def capabilities():
    return {name: dict(implemented=False, enabled=False, variant=None) for name in ('f1', 'f2', 'f3')}


def valid_id(value):
    return type(value) is int and 1 <= value <= MAX_REQUEST_ID


def valid_username(value):
    return isinstance(value, str) and re.fullmatch(r'[A-Za-z0-9_]{1,24}', value) is not None


def valid_text(value):
    if not isinstance(value, str) or not value.strip():
        return False
    try:
        return (1 <= len(value.encode('utf-8')) <= MAX_TEXT_BYTES and
                all(ch in '\t\n' or unicodedata.category(ch) not in ('Cc', 'Cf', 'Cs') for ch in value))
    except UnicodeError:
        return False


def _pairs(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError('Duplicate JSON key.')
        result[key] = value
    return result


def _strict_values(value):
    if isinstance(value, str):
        value.encode('utf-8')
    elif isinstance(value, dict):
        for k, v in value.items():
            _strict_values(k)
            _strict_values(v)
    elif isinstance(value, list):
        for v in value:
            _strict_values(v)
    elif isinstance(value, float) and not math.isfinite(value):
        raise ValueError('Non-finite JSON number.')


def decode_payload(payload: bytes) -> Envelope | ProtocolError:
    try:
        obj = json.loads(payload.decode('utf-8'), object_pairs_hook=_pairs)
        _strict_values(obj)
    except (ValueError, UnicodeError, RecursionError):
        return ProtocolError('INVALID_JSON')
    if not isinstance(obj, dict):
        return ProtocolError('INVALID_ENVELOPE')
    if 'request_id' in obj and obj['request_id'] is not None and type(obj['request_id']) is not int:
        return ProtocolError('BAD_REQUEST_ID')
    if (set(obj) != {'v', 'type', 'request_id', 'data'} or type(obj.get('v')) is not int or
            not isinstance(obj.get('type'), str) or not isinstance(obj.get('data'), dict)):
        return ProtocolError('INVALID_ENVELOPE')
    return Envelope(**obj)


def _uuid(value):
    try:
        return isinstance(value, str) and str(UUID(value)) == value
    except (ValueError, AttributeError):
        return False


def _features(value):
    if not isinstance(value, Mapping) or set(value) != {'f1', 'f2', 'f3'}:
        return False
    for name, state in value.items():
        if not isinstance(state, Mapping) or set(state) != {'implemented', 'enabled', 'variant'}:
            return False
        if type(state['implemented']) is not bool or type(state['enabled']) is not bool:
            return False
        if state['enabled'] and not state['implemented']:
            return False
        variant = state['variant']
        if variant is not None and not isinstance(variant, str):
            return False
        if (name != 'f3' or not state['implemented']) and variant is not None:
            return False
    return True


def validate_message(envelope: Envelope, direction) -> WireMessage | AppError:
    kind, d, rid = envelope.type, envelope.data, envelope.request_id
    allowed = CLIENT_TYPES if direction == 'c2s' else SERVER_TYPES
    if kind not in CLIENT_TYPES | SERVER_TYPES:
        return AppError('UNKNOWN_TYPE', 'Unknown message type.')
    if kind not in allowed:
        return AppError('WRONG_DIRECTION', 'Message is not allowed in this direction.')
    bad = AppError('BAD_REQUEST', 'Invalid message fields.')
    if not isinstance(d, Mapping):
        return bad
    keys = {
        'register': {'username'}, 'broadcast_send': {'text'}, 'private_send': {'to', 'text'},
        'enhancement_request': set(), 'disconnect': set(),
        'hello': {'session_id', 'registration_required', 'max_frame_bytes', 'max_text_bytes', 'registration_timeout_s', 'features'},
        'registered': {'session_id', 'username', 'features'},
        'chat_message': {'message_id', 'mode', 'sender', 'recipient', 'text'},
        'send_result': {'message_id', 'status', 'selected_count', 'queued_count', 'not_queued_count'},
        'bye': {'reason'}, 'error': {'code', 'message', 'fatal', 'feature'},
    }
    if set(d) != keys[kind]:
        return bad
    if kind == 'register' and not valid_username(d['username']):
        return AppError('INVALID_USERNAME', 'Use 1–24 ASCII letters, digits or underscores.')
    if kind in ('broadcast_send', 'private_send') and not valid_text(d['text']):
        return bad
    if kind == 'private_send' and not valid_username(d['to']):
        return bad
    if kind in ('hello', 'registered'):
        if not _uuid(d['session_id']) or not _features(d['features']):
            return bad
    if kind == 'hello':
        if (rid is not None or d['registration_required'] is not True or
                type(d['max_frame_bytes']) is not int or d['max_frame_bytes'] != 65536 or
                type(d['max_text_bytes']) is not int or d['max_text_bytes'] != 4096 or
                type(d['registration_timeout_s']) not in (float, int) or
                not math.isfinite(d['registration_timeout_s']) or d['registration_timeout_s'] <= 0):
            return bad
    if kind == 'registered' and (not valid_id(rid) or not valid_username(d['username'])):
        return bad
    if kind == 'chat_message':
        if (rid is not None or not _uuid(d['message_id']) or not valid_username(d['sender']) or
                not valid_text(d['text']) or d['mode'] not in ('broadcast', 'private') or
                (d['mode'] == 'broadcast' and d['recipient'] is not None) or
                (d['mode'] == 'private' and not valid_username(d['recipient']))):
            return bad
    if kind == 'send_result':
        counts = [d[k] for k in ('selected_count', 'queued_count', 'not_queued_count')]
        if not valid_id(rid) or not _uuid(d['message_id']) or any(type(v) is not int or v < 0 for v in counts):
            return bad
        selected, queued, not_queued = counts
        status = 'queued' if queued == selected else ('not_queued' if queued == 0 else 'partial')
        if selected < 1 or queued + not_queued != selected or d['status'] != status:
            return bad
    if kind == 'bye' and (d['reason'] not in ('client_request', 'server_shutdown') or
                          (d['reason'] == 'client_request' and not valid_id(rid))):
        return bad
    if kind == 'error' and (not isinstance(d['code'], str) or not d['code'] or
                            not isinstance(d['message'], str) or type(d['fatal']) is not bool or
                            d['feature'] not in (None, 'f1', 'f2', 'f3')):
        return bad
    return WireMessage(envelope.v, kind, rid, d)


def make_message(kind, request_id, data) -> WireMessage:
    direction = 'c2s' if kind in CLIENT_TYPES else 's2c'
    result = validate_message(Envelope(1, kind, request_id, data), direction)
    if isinstance(result, AppError):
        raise ValueError(result.message)
    return result


def error_message(error: AppError, request_id: int | None) -> WireMessage:
    return make_message('error', request_id, dict(code=error.code, message=error.message,
                                                fatal=error.fatal, feature=error.feature))
