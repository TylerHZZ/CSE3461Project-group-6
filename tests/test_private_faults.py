"""Deterministic slow-writer fixtures around real localhost TCP connections."""
import io
import json
import threading
import unittest
from unittest.mock import patch

from cse3461_chat.telemetry import EventSink
from cse3461_chat.transport import FramedConnection
from tests.support import running_server, receive
from tests.test_private import enabled_handlers, private_frame, wait_until


class PrivateFaultTests(unittest.TestCase):
    def test_full_recipient_queue_does_not_stall_healthy_private_delivery(self):
        entered, release = threading.Event(), threading.Event()
        original_write = FramedConnection.write
        def slow_write(channel,message):
            if message.type == 'chat_message' and message.data['recipient'] == 'bob':
                entered.set()
                if not release.wait(5):
                    raise OSError('Slow-writer fixture deadline expired.')
            return original_write(channel,message)
        stream=io.StringIO()
        sink=EventSink('server',stream=stream)
        with patch.object(FramedConnection,'write',slow_write), running_server(events=sink,handlers=enabled_handlers()) as (server,connect):
            alice,_=connect('alice')
            bob,hello=connect('bob')
            carol,_=connect('carol')
            try:
                alice.socket.sendall(private_frame(2,'in flight'))
                self.assertTrue(entered.wait(2))
                self.assertEqual(receive(alice).data['status'],'queued')
                for rid in range(3,67):
                    alice.socket.sendall(private_frame(rid,'queued behind slow writer'))
                    self.assertEqual(receive(alice).data['status'],'queued')
                alice.socket.sendall(private_frame(67,'queue full'))
                reply=receive(alice)
                self.assertEqual((reply.type,reply.data['status'],reply.data['queued_count']),('send_result','not_queued',0))
                self.assertIsNone(server.manager.directory.find('bob'))
                self.assertIsNone(receive(bob))
                # This completes while Bob's sole writer is STILL held by the fixture.
                alice.socket.sendall(private_frame(68,'healthy connection continues','carol'))
                result=receive(alice)
                msg=receive(carol)
                self.assertEqual(result.data['status'],'queued')
                self.assertEqual(msg.data['text'],'healthy connection continues')
                self.assertEqual(msg.data['message_id'],result.data['message_id'])
                rows=[json.loads(line) for line in stream.getvalue().splitlines()]
                bob_id=hello.data['session_id']
                self.assertTrue(any(r['event']=='outbound_not_queued' and r['fields'].get('target_session_id')==bob_id and r['fields']['reason']=='full' for r in rows))
                self.assertEqual(sum(r['event']=='outbound_discarded' and r['fields'].get('target_session_id')==bob_id for r in rows),64)
            finally:
                release.set()

    def test_write_failure_after_admission_is_logged_and_isolated(self):
        entered, release = threading.Event(), threading.Event()
        original_write=FramedConnection.write
        def hold_write(channel,message):
            if message.type=='chat_message' and message.data['recipient']=='bob':
                entered.set()
                if not release.wait(3):
                    raise OSError('Writer fixture deadline expired.')
            return original_write(channel,message)
        stream=io.StringIO()
        sink=EventSink('server',stream=stream)
        with patch.object(FramedConnection,'write',hold_write), running_server(events=sink,handlers=enabled_handlers()) as (server,connect):
            alice,_=connect('alice')
            bob,hello=connect('bob')
            carol,_=connect('carol')
            try:
                alice.socket.sendall(private_frame(2,'admitted but never delivered'))
                self.assertTrue(entered.wait(2))
                result=receive(alice)
                self.assertEqual(result.data['status'],'queued')
                record=server.manager.get(hello.data['session_id'])
                record.channel.close()  # Actual socket abort before the admitted frame writes.
            finally:
                release.set()
            def failed():
                return any(json.loads(line)['event']=='frame_write_failed' for line in stream.getvalue().splitlines())
            wait_until(failed)
            wait_until(lambda: server.manager.directory.find('bob') is None)
            self.assertIsNone(receive(bob))
            alice.socket.sendall(private_frame(3,'healthy after failure','carol'))
            result=receive(alice)
            msg=receive(carol)
            self.assertEqual((result.data['status'],msg.data['text']),('queued','healthy after failure'))
