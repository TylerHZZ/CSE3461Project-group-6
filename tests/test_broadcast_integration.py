"""F1 integration contracts over real TCP; fault gates control scheduling only."""
import contextlib
import io
import json
import select
import struct
import threading
import unittest
from dataclasses import replace
from unittest.mock import patch

from cse3461_chat.config import ServerConfig, parse_server_args
from cse3461_chat.features import build_handlers
from cse3461_chat.features.broadcast import handle_broadcast
from cse3461_chat.telemetry import EventSink
from cse3461_chat.transport import FramedConnection
from tests.support import running_server, raw_send, receive, free_port
from tests.test_private import wait_until


def frame(rid, text):
    body = json.dumps(dict(v=1, type='broadcast_send', request_id=rid,
                          data=dict(text=text)), ensure_ascii=False).encode()
    return struct.pack('!I', len(body)) + body


class BroadcastIntegrationTests(unittest.TestCase):
    def quiet(self, *channels):
        self.assertFalse(select.select([c.socket for c in channels], [], [], .08)[0])

    def result(self, channel, rid, counts=(2, 2, 0), status='queued'):
        reply = receive(channel)
        self.assertEqual((reply.type, reply.request_id), ('send_result', rid))
        self.assertEqual(tuple(reply.data[k] for k in ('selected_count', 'queued_count', 'not_queued_count')), counts)
        self.assertEqual(reply.data['status'], status)
        return reply.data['message_id']

    def chat(self, channel, mid, text, sender='alice'):
        message = receive(channel)
        self.assertEqual((message.type, message.request_id), ('chat_message', None))
        self.assertEqual(dict(message.data), dict(message_id=mid, mode='broadcast', sender=sender,
                                                  recipient=None, text=text))

    def test_long_unicode_split_header_payload_and_coalesced_frames(self):
        # Detects truncation, premature UTF-8 decoding and dropped TCP frames.
        with running_server(handlers=build_handlers('f1,f2')) as (_, connect):
            alice, _ = connect('alice'); bob, _ = connect('bob'); carol, _ = connect('carol')
            for rid, text in [(2, 'x'*300), (3, '🙂'*1024), (4, 'x'*4096)]:
                alice.socket.sendall(frame(rid, text))
                mid = self.result(alice, rid)
                for target in (bob, carol): self.chat(target, mid, text)
            payload = frame(5, '你好🙂 fragmented')
            pos = payload.index('你'.encode())
            cuts = [0, 1, 2, 3, 4, pos+1, pos+2, len(payload)-4, len(payload)]
            for start, end in zip(cuts, cuts[1:]):
                alice.socket.sendall(payload[start:end])
                if end < len(payload): self.quiet(alice, bob, carol)
            mid = self.result(alice, 5)
            for target in (bob, carol): self.chat(target, mid, '你好🙂 fragmented')
            alice.socket.sendall(frame(6, 'one')+frame(7, 'two'))
            ids = [self.result(alice, rid) for rid in (6, 7)]
            self.assertEqual(len(set(ids)), 2)
            for target in (bob, carol):
                for mid, text in zip(ids, ('one', 'two')): self.chat(target, mid, text)
            raw_send(bob, 'broadcast_send', 2, {'text':'回复'})
            mid = self.result(bob, 2)
            for target in (alice, carol): self.chat(target, mid, '回复', 'bob')
            raw_send(alice, 'broadcast_send', 8, {'text':'🙂'*1024+'x'})
            self.assertEqual(receive(alice).data['code'], 'BAD_REQUEST')
            self.quiet(alice, bob, carol)

    def test_simultaneous_senders_preserve_each_sender_fifo_without_global_order(self):
        # A shared/misrouted sender ID or reordering must fail at both recipients.
        with running_server(handlers=build_handlers('f1')) as (_, connect):
            channels = {n:connect(n)[0] for n in ('alice', 'bob', 'carol')}
            barrier = threading.Barrier(3)
            failures = []; rows = {}
            def produce(name):
                try:
                    barrier.wait(2)
                    channels[name].socket.sendall(b''.join(frame(i+2, f'{name}-{i}') for i in range(12)))
                    rows[name] = [receive(channels[name]) for _ in range(24)]
                except BaseException as exc: failures.append(exc)
            workers = [threading.Thread(target=produce, args=(n,)) for n in ('alice', 'bob')]
            for w in workers: w.start()
            barrier.wait(2)
            rows['carol'] = [receive(channels['carol']) for _ in range(24)]
            for w in workers: w.join(4); self.assertFalse(w.is_alive())
            self.assertEqual(failures, [])
            for sender, other in [('alice', 'bob'), ('bob', 'alice')]:
                replies = [m for m in rows[sender] if m.type == 'send_result']
                self.assertEqual([m.request_id for m in replies], list(range(2, 14)))
                self.assertTrue(all(m.data['selected_count']==2 and m.data['queued_count']==2 for m in replies))
                for target in (other, 'carol'):
                    chats = [m for m in rows[target] if m.type=='chat_message' and m.data['sender']==sender]
                    self.assertEqual([m.data['text'] for m in chats], [f'{sender}-{i}' for i in range(12)])
                    self.assertEqual([m.data['message_id'] for m in chats], [m.data['message_id'] for m in replies])
                self.assertFalse(any(m.type=='chat_message' and m.data['sender']==sender for m in rows[sender]))
            self.assertEqual(len({m.data['message_id'] for m in rows['carol']}), 24)
            self.quiet(*channels.values())

    def test_lookup_snapshot_excludes_later_join_and_same_name_reconnect(self):
        self.snapshot_case(all_depart=False)

    def test_all_captured_sessions_depart_returns_not_queued(self):
        self.snapshot_case(all_depart=True)

    def snapshot_case(self, all_depart):
        captured, release = threading.Event(), threading.Event()
        def hold(ctx, request):
            outcome = handle_broadcast(ctx, request)
            if request.text == 'old':
                captured.set()
                if not release.wait(4): raise AssertionError('snapshot gate timeout')
            return outcome
        handlers = replace(build_handlers('f1,f2'), broadcast=hold)
        with running_server(handlers=handlers) as (server, connect):
            alice, _ = connect('alice'); bob, old = connect('bob'); carol, _ = connect('carol')
            raw_send(alice, 'broadcast_send', 2, {'text':'old'})
            try:
                self.assertTrue(captured.wait(2))
                bob.close()
                if all_depart: carol.close()
                wait_until(lambda: server.manager.directory.find('bob') is None and
                           (not all_depart or server.manager.directory.find('carol') is None))
                new_bob, new = connect('bob'); dave, _ = connect('dave')
                self.assertNotEqual(old.data['session_id'], new.data['session_id'])
            finally: release.set()
            mid = self.result(alice, 2, (2, 0, 2) if all_depart else (2, 1, 1),
                              'not_queued' if all_depart else 'partial')
            if not all_depart: self.chat(carol, mid, 'old')
            self.quiet(alice, new_bob, dave)
            targets = (new_bob, dave) if all_depart else (new_bob, carol, dave)
            raw_send(alice, 'broadcast_send', 3, {'text':'new'})
            mid = self.result(alice, 3, (len(targets), len(targets), 0))
            for target in targets: self.chat(target, mid, 'new')

    def test_full_broadcast_queue_closes_only_slow_recipient_and_reports_partial(self):
        # Keep actual manager/queues/sockets; hold only Bob's socket write scheduling.
        entered, release = threading.Event(), threading.Event()
        original = FramedConnection.write
        slow = []
        def hold(channel, message):
            if channel in slow and message.type=='chat_message':
                entered.set()
                if not release.wait(8): raise OSError('slow writer gate timeout')
            return original(channel, message)
        with patch.object(FramedConnection, 'write', hold), running_server(handlers=build_handlers('f1')) as (server, connect):
            alice, _ = connect('alice'); bob, hello = connect('bob'); carol, _ = connect('carol')
            slow.append(server.manager.get(hello.data['session_id']).channel)
            try:
                for rid in range(2, 67):
                    raw_send(alice, 'broadcast_send', rid, {'text':f'm{rid}'})
                    mid = self.result(alice, rid)
                    self.chat(carol, mid, f'm{rid}')
                    if rid == 2: self.assertTrue(entered.wait(2))
                raw_send(alice, 'broadcast_send', 67, {'text':'overflow'})
                mid = self.result(alice, 67, (2, 1, 1), 'partial')
                self.chat(carol, mid, 'overflow')
                self.assertIsNone(server.manager.directory.find('bob'))
                self.assertIsNone(receive(bob))
                self.assertGreaterEqual(server.manager.discarded, 64)
                raw_send(alice, 'broadcast_send', 68, {'text':'healthy'})
                self.chat(carol, self.result(alice, 68, (1, 1, 0)), 'healthy')
            finally: release.set()

    def test_enabled_broadcast_does_not_turn_private_errors_into_broadcasts(self):
        with running_server(handlers=build_handlers('f1,f2')) as (_, connect):
            alice, _ = connect('alice'); bob, _ = connect('bob'); carol, _ = connect('carol')
            for rid, data, code in [(2, {'to':'missing','text':'secret'}, 'USER_NOT_FOUND'),
                                    (3, {'to':'alice','text':'secret'}, 'SELF_TARGET'),
                                    (4, {'text':'secret'}, 'BAD_REQUEST')]:
                raw_send(alice, 'private_send', rid, data)
                self.assertEqual(receive(alice).data['code'], code)
            self.quiet(alice, bob, carol)
            raw_send(alice, 'private_send', 5, {'to':'bob','text':'only bob'})
            mid = self.result(alice, 5, (1, 1, 0))
            msg = receive(bob)
            self.assertEqual((msg.data['message_id'], msg.data['mode'], msg.data['text']), (mid, 'private', 'only bob'))
            self.quiet(alice, bob, carol)


class FeatureCombinationTests(unittest.TestCase):
    def test_all_eight_combinations_gate_requests_and_advertise_actual_capabilities(self):
        # Literal subset matrix catches dropping any preexisting producer or F3.
        for features in ('none','f1','f2','f3','f1,f2','f1,f3','f2,f3','f1,f2,f3'):
            with self.subTest(features=features):
                selected = features.split(',')
                args = ['--features', features]
                if 'f3' in selected: args += ['--delay-mode','fixed','--delay-ms','0']
                config = replace(parse_server_args(args), port=free_port())
                with running_server(server_config=config) as (_, connect):
                    alice, hello = connect('alice'); bob, _ = connect('bob'); carol, _ = connect('carol')
                    for f in ('f1','f2','f3'):
                        self.assertEqual(hello.data['features'][f], dict(implemented=True, enabled=f in selected, variant='A' if f=='f3' else None))
                    for rid, f, kind, data in [(2,'f1','broadcast_send',{'text':'all'}),
                            (3,'f2','private_send',{'to':'bob','text':'private'}), (4,'f3','enhancement_request',{})]:
                        raw_send(alice, kind, rid, data); reply = receive(alice)
                        if f in selected and f != 'f3':
                            self.assertEqual(reply.type, 'send_result')
                            self.assertEqual(receive(bob).data['text'], data['text'])
                            if f == 'f1': self.assertEqual(receive(carol).data['text'], 'all')
                        else:
                            self.assertEqual(reply.data['code'], 'STARTUP_CONFIG_ONLY' if f in selected else 'FEATURE_DISABLED')
                    self.assertFalse(select.select([c.socket for c in (alice,bob,carol)],[],[],.03)[0])

    def test_f3_mode_validation_survives_all_broadcast_combinations(self):
        cases = [['--features','f1,f3'], ['--features','f1,f2,f3'],
                 ['--features','f1','--delay-mode','fixed'],
                 ['--features','f1,f2','--delay-mode','jitter'],
                 ['--features','f1,f3','--delay-mode','fixed','--jitter-ms','1'],
                 ['--features','f1,f3','--delay-mode','jitter','--delay-ms','nan'],
                 ['--features','f1,f2,f3','--delay-mode','jitter','--delay-ms','900','--jitter-ms','200'],
                 ['--features','f2,f1'], ['--features','f1,f1'], ['--features','none,f1']]
        for args in cases:
            with self.subTest(args=args), contextlib.redirect_stderr(io.StringIO()):
                with self.assertRaises(SystemExit) as err: parse_server_args(args)
                self.assertEqual(err.exception.code, 2)
