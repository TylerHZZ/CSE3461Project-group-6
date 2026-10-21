import socket
import threading
import time
import unittest

from cse3461_chat.protocol import AppError, capabilities, make_message
from cse3461_chat.sessions import SessionManager, SessionView
from cse3461_chat.telemetry import EventSink
from cse3461_chat.transport import FramedConnection


class SessionTests(unittest.TestCase):
    def setUp(self):
        self.manager = SessionManager(16, EventSink('server'))
        self.records = []

    def tearDown(self):
        for record in self.records:
            self.manager.close(record.session_id, 'test_end', None, False)
        for record in self.records:
            if record.writer:
                record.writer.join(2)

    def attach(self, accepted_ns=None):
        a, b = socket.socketpair()
        self.addCleanup(b.close)
        record = self.manager.attach(FramedConnection(a), ('127.0.0.1', 1234),
                                     accepted_ns or time.monotonic_ns())
        if record is None:
            a.close()
        else:
            self.records.append(record)
        return record, FramedConnection(b)

    def register(self, record, username='bob', rid=1):
        reply = make_message('registered', rid, dict(session_id=record.session_id, username=username,
                                                    features=capabilities()))
        return self.manager.register(record.session_id, username, reply)

    def test_atomic_registration_and_deadline(self):
        a, _ = self.attach()
        b, _ = self.attach()
        barrier = threading.Barrier(3)
        results = []
        def claim(s):
            barrier.wait()
            results.append(self.register(s))
        threads = [threading.Thread(target=claim, args=(s,)) for s in (a,b)]
        for t in threads:
            t.start()
        barrier.wait()
        for t in threads:
            t.join(2)
        self.assertEqual(sum(isinstance(r, SessionView) for r in results), 1)
        self.assertEqual([r.code for r in results if isinstance(r, AppError)], ['USERNAME_TAKEN'])
        c, _ = self.attach(time.monotonic_ns()-31_000_000_000)
        self.assertEqual(self.register(c, 'carol').code, 'REGISTRATION_TIMEOUT')
        deadline = b.registration_deadline_ns
        self.manager.register(b.session_id, 'bad name', make_message('disconnect', 1, {}))
        self.assertEqual(b.registration_deadline_ns, deadline)

    def test_registered_reply_precedes_visibility(self):
        s, _ = self.attach()
        self.assertIsNone(self.manager.directory.find('bob'))
        self.assertIsInstance(self.register(s), SessionView)
        visible = self.manager.directory.find('bob')
        self.assertEqual(s.outbound.get_nowait().message.type, 'registered')
        self.assertEqual(visible.session_id, s.session_id)

    def test_directory_snapshots(self):
        a, _ = self.attach()
        b, _ = self.attach()
        c, _ = self.attach()
        self.register(a, 'alice')
        self.register(b, 'bob')
        snapshot = self.manager.directory.others(a.session_id)
        self.assertEqual([v.username for v in snapshot], ['bob'])
        self.assertFalse(hasattr(snapshot[0], 'socket'))
        self.manager.close(b.session_id, 'quit', None, False)
        self.assertEqual(self.manager.directory.others(a.session_id), ())
        self.assertEqual(snapshot[0].username, 'bob')

    def test_stale_cleanup_preserves_replacement(self):
        old, _ = self.attach()
        self.register(old)
        self.manager.close(old.session_id, 'quit', None, False)
        new, _ = self.attach()
        self.register(new)
        self.manager.close(old.session_id, 'late_cleanup', None, False)
        self.assertEqual(self.manager.directory.find('bob').session_id, new.session_id)
        self.assertEqual(self.manager.enqueue(old.session_id, make_message('disconnect', 1, {}), None).reason, 'closed')

    def test_full_queue_isolates_connection(self):
        slow, _ = self.attach()
        healthy, _ = self.attach()
        msg = make_message('error', 1, dict(code='BAD_REQUEST', message='Invalid', fatal=False, feature=None))
        for _ in range(64):
            self.assertTrue(self.manager.enqueue(slow.session_id, msg, None).queued)
        self.assertEqual(self.manager.enqueue(slow.session_id, msg, None).reason, 'full')
        self.assertIsInstance(self.register(slow), AppError)
        self.assertIsNone(self.manager.directory.find('bob'))
        self.manager.close(slow.session_id, 'queue_full', None, False)
        self.assertIsInstance(self.register(healthy, 'alice'), SessionView)
        self.assertTrue(self.manager.enqueue(healthy.session_id, msg, None).queued)

    def test_concurrent_control_frames(self):
        s, peer = self.attach()
        s.writer = threading.Thread(target=self.manager.writer_loop, args=(s,))
        s.writer.start()
        def produce(start):
            for rid in range(start, start+10):
                msg = make_message('error', rid, dict(code='BAD_REQUEST', message='Invalid', fatal=False, feature=None))
                self.assertTrue(self.manager.enqueue(s.session_id, msg, None).queued)
        producers = [threading.Thread(target=produce, args=(i*10+1,)) for i in range(4)]
        for t in producers:
            t.start()
        ids = [peer.receive(time.monotonic_ns()+2_000_000_000).request_id for _ in range(40)]
        for t in producers:
            t.join(2)
        self.assertEqual(sorted(ids), list(range(1,41)))
        for group in range(4):
            self.assertEqual([i for i in ids if group*10 < i <= (group+1)*10], list(range(group*10+1, (group+1)*10+1)))

    def test_capacity_counts_unregistered(self):
        self.manager = SessionManager(2, EventSink('server'))
        a, _ = self.attach()
        b, _ = self.attach()
        c, _ = self.attach()
        self.assertIsNone(c)
        self.manager.close(a.session_id, 'quit', None, False)
        self.manager.maintain()
        d, _ = self.attach()
        self.assertIsNotNone(d)
