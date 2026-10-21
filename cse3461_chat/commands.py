"""Terminal grammar and safe rendering; no socket operations."""
import re
import unicodedata
from dataclasses import dataclass

from .protocol import freeze, valid_text, valid_username


@dataclass(frozen=True)
class ClientCommand:
    kind: str
    type: str | None = None
    data: object = None


@dataclass(frozen=True)
class LocalUsageError:
    message: str


def parse_input(line: str) -> ClientCommand | LocalUsageError:
    if line in ('/help','/quit'):
        return ClientCommand(line[1:])
    if line == '/enhance':
        return ClientCommand('send','enhancement_request',freeze({}))
    if line.startswith('@'):
        match = re.fullmatch(r'@(\S+)\s(.*)',line,re.DOTALL)
        if not match or not valid_username(match[1]) or not valid_text(match[2]):
            return LocalUsageError('Use @username <text>; invalid private input is never broadcast.')
        return ClientCommand('send','private_send',freeze(dict(to=match[1],text=match[2])))
    if line.startswith('/'):
        match = re.fullmatch(r'/all\s(.*)',line,re.DOTALL)
        if not match:
            return LocalUsageError('Unknown or incomplete command. Use /help.')
        line = match[1]
    if not valid_text(line):
        return LocalUsageError('Text must contain 1–4096 UTF-8 bytes, with no unsafe controls.')
    return ClientCommand('send','broadcast_send',freeze({'text':line}))


def safe_display(value) -> str:
    return ''.join(f'\\u{ord(c):04x}' if unicodedata.category(c) in ('Cc','Cf','Cs') else c for c in str(value))


def help_text(features) -> str:
    states = ', '.join(f'{name.upper()}={"enabled" if state["enabled"] else "unavailable"}' for name,state in features.items())
    return ('Commands: text or /all <text>; @username <text>; /enhance; /help; /quit. '
            'Use /all @literal for literal leading @. F3 A is configured at server startup; /enhance cannot change it. '+states+'. Submitted is not delivered.')


def render_event(message) -> str:
    d, kind, rid = message.data, message.type, message.request_id
    if kind == 'hello':
        return f'[hello] session={d["session_id"]}; registration required.'
    if kind == 'registered':
        return f'[registered] {d["username"]}; session={d["session_id"]}; '+help_text(d['features'])
    if kind == 'error':
        return safe_display(f'[error] request={rid} {d["code"]} feature={d["feature"]}: {d["message"]}')
    if kind == 'bye':
        return f'[bye] {d["reason"]}'
    if kind == 'send_result':
        return f'[queue result] request={rid} {d["status"]}; queue admission is not receipt.'
    if kind == 'chat_message':
        return safe_display(f'[{d["mode"]}] {d["sender"]}: {d["text"]}')
    return safe_display(kind)
