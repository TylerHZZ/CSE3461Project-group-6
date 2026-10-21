"""Real socket checks for the F3 hook, cancellation and bounded queues."""
import io
import json
import select
import threading
import time
import unittest
from cse3461_chat.config import ServerConfig
from cse3461_chat.telemetry import EventSink
from tests.support import free_port, running_server, raw_send, receive
from tests.test_private import wait_until


class KeepStream(io.StringIO):
    def close(self):
        pass


class DelayWriterTests(unittest.TestCase):
    def setup_server(self, delay=120, mode='fixed', jitter=0):
        self.stream = KeepStream()
        cfg = ServerConfig(port=free_port(), features='f2,f3', delay_mode=mode,
                           delay_ms=delay, jitter_ms=jitter, delay_seed=19)
        return running_server(server_config=cfg, events=EventSink('server', stream=self.stream))

    def rows(self, event):
        return [r['fields'] for line in self.stream.getvalue().splitlines()
                if (r := json.loads(line))['event'] == event]

    def send(self, alice, rid, target='bob'):
        raw_send(alice, 'private_send', rid, dict(to=target, text=f'body {rid}'))
        result = receive(alice)
        self.assertEqual(result.type, 'send_result')
        return result

    def wait_dequeued(self):
        wait_until(lambda: self.rows('chat_dequeued'))

    def test_only_chat_waits_and_controls_preserve_fifo(self):
        with self.setup_server(150) as (_, connect):
            alice, _ = connect('alice'); bob, _ = connect('bob')
            self.send(alice, 2)
            self.wait_dequeued()
            raw_send(bob, 'enhancement_request', 2, {})
            self.assertFalse(select.select([bob.socket], [], [], .04)[0])
            self.assertEqual(receive(bob).type, 'chat_message')
            self.assertEqual(receive(bob).data['code'], 'STARTUP_CONFIG_ONLY')
            waits = self.rows('chat_delay_completed')
            self.assertEqual(len(waits), 1)
            self.assertEqual(waits[0]['frame_type'], 'chat_message')
            self.assertGreaterEqual(waits[0]['actual_wait_ns'], 140_000_000)
            self.assertFalse(waits[0]['cancelled'])

    def test_fifo_queue_time_is_distinct_from_current_wait(self):
        with self.setup_server(40) as (_, connect):
            alice, _ = connect('alice'); bob, _ = connect('bob')
            ids = [self.send(alice, rid).data['message_id'] for rid in range(2, 7)]
            self.assertEqual([receive(bob).data['message_id'] for _ in ids], ids)
            wait_until(lambda: len(self.rows('chat_delay_completed')) == 5)
            waits = self.rows('chat_delay_completed')
            self.assertGreater(waits[-1]['queue_only_ns'], 100_000_000)
            self.assertTrue(all(w['selected_ms'] == 40 for w in waits))
            writes = [r for r in self.rows('frame_write_completed') if r['frame_type']=='chat_message']
            self.assertTrue(all(r['started_ns'] >= r['enqueued_ns'] for r in writes))

    def test_recipient_waits_are_concurrent_and_directory_stays_responsive(self):
        with self.setup_server(300) as (server, connect):
            alice, _ = connect('alice'); bob, _ = connect('bob')
            self.send(alice, 2); self.wait_dequeued()
            start = time.monotonic()
            carol, _ = connect('carol')
            self.assertIsNotNone(server.manager.directory.find('bob'))
            self.assertLess(time.monotonic()-start, .2)
            self.send(alice, 3, 'carol')
            receive(bob); receive(carol)
            wait_until(lambda: len(self.rows('chat_delay_completed')) == 2)
            a, b = sorted(self.rows('chat_delay_completed'), key=lambda r:r['wait_started_ns'])
            self.assertLess(b['wait_started_ns'], a['wait_ended_ns'])

    def test_server_shutdown_interrupts_wait_and_counts_inflight(self):
        with self.setup_server(1000) as (server, connect):
            alice, _ = connect('alice'); bob, _ = connect('bob')
            self.send(alice, 2); self.wait_dequeued()
            start = time.monotonic(); server.stop('server_shutdown')
            self.assertEqual(receive(bob).type, 'bye')
            self.assertLess(time.monotonic()-start, .6)
            wait_until(lambda: self.rows('chat_delay_completed'))
            self.assertTrue(self.rows('chat_delay_completed')[0]['cancelled'])
            self.assertEqual(server.manager.discarded, 1)
            self.assertEqual(len(self.rows('outbound_discarded')), 1)

    def test_disconnect_cancels_without_replaying_to_replacement(self):
        with self.setup_server(1000) as (server, connect):
            alice, _ = connect('alice'); bob, hello = connect('bob')
            self.send(alice, 2); self.wait_dequeued(); bob.close()
            wait_until(lambda: server.manager.directory.find('bob') is None)
            new, newhello = connect('bob')
            self.assertNotEqual(hello.data['session_id'], newhello.data['session_id'])
            self.assertFalse(select.select([new.socket], [], [], .06)[0])
            wait_until(lambda: self.rows('outbound_discarded'))
            self.assertEqual(self.rows('outbound_discarded')[0]['target_session_id'], hello.data['session_id'])

    def test_f3_queue_full_still_returns_not_queued_and_isolates_recipient(self):
        with self.setup_server(1000) as (server, connect):
            alice, _ = connect('alice'); bob, hello = connect('bob'); carol, _ = connect('carol')
            self.send(alice, 2); self.wait_dequeued()
            for rid in range(3, 67):
                self.assertEqual(self.send(alice, rid).data['status'], 'queued')
            self.assertEqual(self.send(alice, 67).data['status'], 'not_queued')
            self.assertIsNone(server.manager.directory.find('bob'))
            self.assertEqual(self.send(alice, 68, 'carol').data['status'], 'queued')
            self.assertEqual(receive(carol).data['text'], 'body 68')
            wait_until(lambda: server.manager.discarded == 65)
            self.assertEqual(len(self.rows('outbound_discarded')), 65)

    def test_enabled_zero_delivers_and_logs_measured_zero_path(self):
        with self.setup_server(0) as (_, connect):
            alice, _ = connect('alice'); bob, hello = connect('bob')
            self.assertTrue(hello.data['features']['f3']['enabled'])
            self.send(alice, 2)
            self.assertEqual(receive(bob).data['text'], 'body 2')
            wait_until(lambda: self.rows('chat_delay_completed'))
            observation = self.rows('chat_delay_completed')[0]
            self.assertEqual(observation['selected_ms'], 0)
            self.assertEqual(observation['actual_wait_ns'], observation['wait_ended_ns']-observation['wait_started_ns'])

    def test_jitter_on_real_writer_stays_in_selected_range(self):
        with self.setup_server(12, 'jitter', 10) as (_, connect):
            alice, _ = connect('alice'); bob, _ = connect('bob')
            for rid in range(2, 10):
                self.send(alice, rid)
            self.assertEqual([receive(bob).data['text'] for _ in range(8)], [f'body {i}' for i in range(2, 10)])
            wait_until(lambda: len(self.rows('chat_delay_completed')) == 8)
            values = [r['selected_ms'] for r in self.rows('chat_delay_completed')]
            self.assertTrue(all(2 <= v <= 22 for v in values))
            self.assertGreater(len(set(values)), 1)

    def test_requested_logging_failure_during_wait_stops_server(self):
        class FailingStream(KeepStream):
            def write(self, text):
                if '"event": "chat_delay_completed"' in text:
                    raise OSError('Injected disk failure at F3 event')
                return super().write(text)
        self.stream = FailingStream()
        events = EventSink('server', stream=self.stream)
        cfg = ServerConfig(port=free_port(), features='f2,f3', delay_mode='fixed', delay_ms=20)
        with running_server(server_config=cfg, events=events) as (server, connect):
            alice, _ = connect('alice'); bob, _ = connect('bob')
            self.send(alice, 2)
            wait_until(lambda: events.failed.is_set())
            wait_until(lambda: not server.manager.records())
            self.assertFalse(events.valid)
            self.assertEqual(server.reason, 'telemetry_failure')
