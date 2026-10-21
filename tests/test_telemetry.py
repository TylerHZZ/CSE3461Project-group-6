import json
import tempfile
import threading
import unittest
from pathlib import Path
from uuid import UUID
from cse3461_chat.telemetry import open_event_sink, TelemetryError


class TelemetryTests(unittest.TestCase):
    def test_jsonl_sequence_and_metadata(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder)/'events.jsonl'
            sink = open_event_sink('server', 'test-run', str(path))
            threads = [threading.Thread(target=lambda: [sink.emit('request_received', {'request_id': i, 'received_ns': 123}) for i in range(20)]) for _ in range(4)]
            for t in threads:
                t.start()
            for t in threads:
                t.join(2)
            sink.close()
            rows = [json.loads(line) for line in path.read_text().splitlines()]
            self.assertEqual(len(rows), 80)
            self.assertEqual([row['seq'] for row in rows], list(range(1, 81)))
            for row in rows:
                self.assertEqual(set(row), {'schema_version','run_id','process_id','seq','utc_time','monotonic_ns','role','event','fields'})
                self.assertEqual(row['schema_version'], 1)
                self.assertEqual(row['run_id'], 'test-run')
                self.assertEqual(row['fields']['received_ns'], 123)
                self.assertEqual(str(UUID(row['process_id'])), row['process_id'])
                self.assertNotIn('text', row['fields'])

    def test_log_open_failure_precedes_network(self):
        with tempfile.TemporaryDirectory() as folder:
            with self.assertRaises(TelemetryError):
                open_event_sink('client', None, folder)

    def test_runtime_log_failure_is_visible(self):
        with tempfile.TemporaryDirectory() as folder:
            sink = open_event_sink('server', None, str(Path(folder)/'events.jsonl'))
            sink._stream.close()  # Inject an actual closed-file write, not a mocked sink.
            with self.assertRaises(TelemetryError):
                sink.emit('process_started', {})
            self.assertFalse(sink.valid)
            self.assertTrue(sink.failed.is_set())
            sink.close()
