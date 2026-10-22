"""Immutable startup configuration; only implemented features can be enabled."""
import argparse
import math
import socket
from dataclasses import dataclass

from .protocol import valid_username

CONNECT_S = 5.0
HELLO_S = 5.0
REGISTRATION_S = 30.0
REQUEST_S = 10.0
DRAIN_S = 2.0
SHUTDOWN_S = 5.0
OUTBOUND_CAPACITY = 64
EVENT_CAPACITY = 64
COMMAND_CAPACITY = 16
MAX_PENDING = 32
FEATURE_CHOICES = ('none', 'f1', 'f2', 'f3', 'f1,f2', 'f1,f3', 'f2,f3', 'f1,f2,f3')


@dataclass(frozen=True)
class ServerConfig:
    host: str = '127.0.0.1'
    port: int = 3461
    max_clients: int = 16
    features: str = 'none'
    delay_mode: str = 'off'
    delay_ms: float = 0.0
    jitter_ms: float = 0.0
    delay_seed: int = 0
    run_id: str | None = None
    log_file: str | None = None


@dataclass(frozen=True)
class ClientConfig:
    host: str = '127.0.0.1'
    port: int = 3461
    username: str | None = None
    run_id: str | None = None
    log_file: str | None = None


def validate_config(config):
    if type(config.port) is not int or not 1 <= config.port <= 65535:
        raise ValueError('Port must be between 1 and 65535.')
    try:
        addresses = socket.getaddrinfo(config.host, config.port, socket.AF_INET, socket.SOCK_STREAM)
    except (OSError, UnicodeError) as exc:
        raise ValueError('Host must resolve to an IPv4 address.') from exc
    if isinstance(config, ServerConfig):
        if type(config.max_clients) is not int or config.max_clients <= 0:
            raise ValueError('max-clients must be positive.')
        if config.features not in FEATURE_CHOICES:
            raise ValueError('Use --features '+', '.join(FEATURE_CHOICES)+'.')
        if config.delay_mode not in ('off', 'fixed', 'jitter'):
            raise ValueError('delay-mode must be off, fixed or jitter.')
        if any(type(v) not in (int, float) or not math.isfinite(v) for v in (config.delay_ms, config.jitter_ms)):
            raise ValueError('Delays must be finite numbers.')
        if not 0 <= config.jitter_ms <= config.delay_ms or config.delay_ms + config.jitter_ms > 1000:
            raise ValueError('Require 0 <= jitter-ms <= delay-ms and delay-ms + jitter-ms <= 1000.')
        if type(config.delay_seed) is not int or not 0 <= config.delay_seed < 2**32:
            raise ValueError('delay-seed must be an integer from 0 to 4294967295.')
        if ('f3' in config.features.split(',')) != (config.delay_mode != 'off'):
            raise ValueError('Enabling f3 requires fixed/jitter mode; delay modes require f3.')
        if config.delay_mode == 'fixed' and config.jitter_ms != 0:
            raise ValueError('Fixed mode requires jitter-ms=0.')
        if config.delay_mode == 'off' and (config.delay_ms != 0 or config.jitter_ms != 0):
            raise ValueError('Off mode requires zero delay-ms and jitter-ms.')
    else:
        if any(row[4][0] == '0.0.0.0' for row in addresses):
            raise ValueError('Use the actual server address, not 0.0.0.0.')
        if config.username is not None and not valid_username(config.username):
            raise ValueError('Username must contain 1–24 ASCII letters, digits or underscores.')


def _parse(argv, server):
    parser = argparse.ArgumentParser(description='CSE3461 framed TCP chat; F1 broadcast, F2 private chat and F3 A delay/jitter available.')
    parser.add_argument('--host', default='127.0.0.1')
    parser.add_argument('--port', type=int, default=3461)
    parser.add_argument('--run-id')
    parser.add_argument('--log-file', help='New per-process JSONL file; parent directory must exist.')
    if server:
        parser.add_argument('--max-clients', type=int, default=16)
        parser.add_argument('--features', default='none', help='none (default) or an ascending comma-separated subset of f1,f2,f3; F3 requires fixed/jitter mode.')
        parser.add_argument('--delay-mode', default='off', help='off, fixed or jitter; chat frames only, FIFO controls can queue behind chat.')
        parser.add_argument('--delay-ms', type=float, default=0.0, help='Fixed delay or jitter center in ms, 0..1000.')
        parser.add_argument('--jitter-ms', type=float, default=0.0, help='Uniform half-width in ms: [delay-jitter, delay+jitter] within 0..1000.')
        parser.add_argument('--delay-seed', type=int, default=0, help='0..4294967295; independent sequence per recipient username.')
    else:
        parser.add_argument('--username')
    config = (ServerConfig if server else ClientConfig)(**vars(parser.parse_args(argv)))
    try:
        validate_config(config)
    except ValueError as exc:
        parser.error(str(exc))
    return config


def parse_server_args(argv=None) -> ServerConfig:
    return _parse(argv, True)


def parse_client_args(argv=None) -> ClientConfig:
    return _parse(argv, False)
