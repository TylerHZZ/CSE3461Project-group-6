"""Immutable startup configuration; only implemented features can be enabled."""
import argparse
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


@dataclass(frozen=True)
class ServerConfig:
    host: str = '127.0.0.1'
    port: int = 3461
    max_clients: int = 16
    features: str = 'none'
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
        if config.features not in ('none', 'f2'):
            raise ValueError('Use --features none or --features f2; F1/F3 are not implemented.')
    else:
        if any(row[4][0] == '0.0.0.0' for row in addresses):
            raise ValueError('Use the actual server address, not 0.0.0.0.')
        if config.username is not None and not valid_username(config.username):
            raise ValueError('Username must contain 1–24 ASCII letters, digits or underscores.')


def _parse(argv, server):
    parser = argparse.ArgumentParser(description='CSE3461 framed TCP chat; F2 available, F1/F3 unimplemented.')
    parser.add_argument('--host', default='127.0.0.1')
    parser.add_argument('--port', type=int, default=3461)
    parser.add_argument('--run-id')
    parser.add_argument('--log-file', help='New per-process JSONL file; parent directory must exist.')
    if server:
        parser.add_argument('--max-clients', type=int, default=16)
        parser.add_argument('--features', default='none', help='none (default) disables chat; f2 enables private messaging.')
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
