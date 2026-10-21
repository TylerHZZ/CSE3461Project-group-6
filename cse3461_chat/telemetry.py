"""Per-process JSONL evidence. Requested logging fails visibly and closed."""
import json
import platform
import threading
import time
from dataclasses import asdict
from datetime import datetime, timezone
from uuid import uuid4

from .protocol import capabilities, thaw


class TelemetryError(OSError):
    pass


class EventSink:
    def __init__(self, role, run_id=None, stream=None):
        self.role = role
        self.run_id = run_id or str(uuid4())
        self.process_id = str(uuid4())
        self._stream = stream
        self._lock = threading.Lock()
        self._seq = 0
        self.valid = True
        self.failed = threading.Event()

    def emit(self, name: str, fields: object) -> None:
        with self._lock:
            if not self.valid:
                raise TelemetryError('Requested telemetry is unavailable; evidence is invalid.')
            self._seq += 1
            row = dict(schema_version=1, run_id=self.run_id, process_id=self.process_id,
                       seq=self._seq, utc_time=datetime.now(timezone.utc).isoformat(),
                       monotonic_ns=time.monotonic_ns(), role=self.role, event=name, fields=thaw(fields))
            if self._stream is not None:
                try:
                    self._stream.write(json.dumps(row, ensure_ascii=True, allow_nan=False)+'\n')
                    self._stream.flush()
                except (OSError, ValueError, TypeError) as exc:
                    self.valid = False
                    self.failed.set()
                    raise TelemetryError('Could not record requested telemetry; evidence is invalid.') from exc

    def close(self) -> None:
        with self._lock:
            if self._stream is not None:
                try:
                    self._stream.close()
                except OSError as exc:
                    self.valid = False
                    self.failed.set()
                    raise TelemetryError('Could not close telemetry; evidence is invalid.') from exc
                finally:
                    self._stream = None


def open_event_sink(role, run_id, log_file) -> EventSink:
    try:
        stream = open(log_file, 'x', encoding='utf-8') if log_file else None
    except OSError as exc:
        raise TelemetryError('Cannot create requested log file; use a new writable path.') from exc
    return EventSink(role, run_id, stream)


def process_metadata(config, descriptors=None):
    return dict(config=asdict(config), protocol_version=1, python_version=platform.python_version(),
                os=platform.platform(), capabilities=capabilities(descriptors), run_mode='unspecified')
