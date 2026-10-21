"""F2 wire regressions: truncation, framing, privacy and session identity."""
import json
import select
import struct
import threading
import time
import unittest
from dataclasses import replace

from cse3461_chat.features import build_handlers
from cse3461_chat.features.private_chat import handle_private
from cse3461_chat.protocol import FeatureDescriptor
from tests.support import running_server, raw_send, receive, ProcessClient


def enabled_handlers(**overrides):
    return replace(build_handlers(), descriptors=(FeatureDescriptor('f1'),
        FeatureDescriptor('f2', True, True), FeatureDescriptor('f3')), **overrides)


def private_frame(rid, text, target='bob'):
    # Independently encode the test input; do not use the production frame encoder.
    body = json.dumps(dict(v=1, type='private_send', request_id=rid,
                          data=dict(to=target, text=text)), ensure_ascii=False).encode('utf-8')
    return struct.pack('!I', len(body)) + body


def wait_until(predicate, seconds=2):
    deadline = time.monotonic() + seconds
    while time.monotonic() < deadline:
        if predicate():
            return
        time.sleep(.005)
    raise AssertionError('Condition did not become true before deadline.')


class PrivateWireTests(unittest.TestCase):
    def assert_quiet(self, *channels):
        self.assertFalse(select.select([c.socket for c in channels], [], [], .1)[0],
                         'Unexpected notification, echo, error, or duplicate frame.')

    def result(self, sender, rid, queued=1):
        reply = receive(sender)
        self.assertEqual((reply.type, reply.request_id), ('send_result', rid))
        self.assertEqual((reply.data['status'], reply.data['selected_count'],
                          reply.data['queued_count'], reply.data['not_queued_count']),
                         ('queued' if queued else 'not_queued', 1, queued, 1-queued))
        return reply.data['message_id']

    def message(self, recipient, message_id, text, sender='alice', target='bob'):
        msg = receive(recipient)
        self.assertEqual((msg.type, msg.request_id), ('chat_message', None))
        self.assertEqual(dict(msg.data), dict(message_id=message_id, mode='private',
            sender=sender, recipient=target, text=text))

    def test_300_byte_body_is_complete_and_private(self):
        # Fails if publication truncates to the old 200-byte recv buffer or echoes.
        with running_server(handlers=enabled_handlers()) as (_, connect):
            alice, _ = connect('alice')
            bob, _ = connect('bob')
            carol, _ = connect('carol')
            alice.socket.sendall(private_frame(2, 'x'*300))
            self.message(bob, self.result(alice, 2), 'x'*300)
            self.assert_quiet(alice, bob, carol)

    def test_fragmented_body_waits_for_complete_frame(self):
        # Fails if any recv chunk is dispatched as a complete logical message.
        with running_server(handlers=enabled_handlers()) as (_, connect):
            alice, _ = connect('alice')
            bob, _ = connect('bob')
            carol, _ = connect('carol')
            frame = private_frame(2, 'fragmented')
            split = frame.index(b'fragmented') + len(b'frag')
            alice.socket.sendall(frame[:split])
            self.assertFalse(select.select([alice.socket,bob.socket,carol.socket],[],[],.25)[0])
            alice.socket.sendall(frame[split:])
            self.message(bob, self.result(alice, 2), 'fragmented')
            self.assert_quiet(alice, bob, carol)

    def test_split_headers_utf8_and_coalesced_frames(self):
        # Detects lost byte state, premature UTF-8 decoding and dropped coalesced frames.
        with running_server(handlers=enabled_handlers()) as (_, connect):
            alice, _ = connect('alice')
            bob, _ = connect('bob')
            carol, _ = connect('carol')
            frame = private_frame(2, '你好🙂 split')
            utf8 = frame.index('你'.encode())
            cuts = [0, 1, 2, 3, 4, utf8+1, utf8+2, len(frame)]
            for start, end in zip(cuts, cuts[1:]):
                alice.socket.sendall(frame[start:end])
                if end != len(frame):
                    self.assertFalse(select.select([alice.socket,bob.socket],[],[],.02)[0])
            self.message(bob, self.result(alice, 2), '你好🙂 split')
            alice.socket.sendall(private_frame(3, 'first')+private_frame(4, 'second'))
            ids = [self.result(alice, rid) for rid in (3,4)]
            self.assertEqual(len(set(ids)), 2)
            for mid, text in zip(ids, ('first','second')):
                self.message(bob, mid, text)
            self.assert_quiet(alice,bob,carol)

    def test_utf8_byte_limit_and_oversized_frame_rejection(self):
        with running_server(handlers=enabled_handlers()) as (_, connect):
            alice, _ = connect('alice')
            bob, _ = connect('bob')
            carol, _ = connect('carol')
            for rid, text in [(2,'x'*4096),(3,'🙂'*1024)]:
                alice.socket.sendall(private_frame(rid,text))
                self.message(bob,self.result(alice,rid),text)
            for rid, text in [(4,'x'*4097),(5,'🙂'*1024+'x')]:
                alice.socket.sendall(private_frame(rid,text))
                reply = receive(alice)
                self.assertEqual((reply.request_id,reply.data['code'],reply.data['fatal']),
                                 (rid,'BAD_REQUEST',False))
            self.assert_quiet(alice,bob,carol)
            alice.socket.sendall(struct.pack('!I',65537))
            reply = receive(alice)
            self.assertEqual((reply.data['code'],reply.data['fatal']),('FRAME_TOO_LARGE',True))
            self.assertIsNone(receive(alice))
            bob.socket.sendall(private_frame(2,'still healthy','carol'))
            self.message(carol,self.result(bob,2),'still healthy','bob','carol')

    def test_bidirectional_errors_and_unavailable_features(self):
        with running_server(handlers=enabled_handlers()) as (_, connect):
            alice, hello = connect('alice')
            bob, _ = connect('bob')
            carol, _ = connect('carol')
            self.assertEqual(hello.data['features']['f2'],dict(implemented=True,enabled=True,variant=None))
            bob.socket.sendall(private_frame(2,'中文回复','alice'))
            self.message(alice,self.result(bob,2),'中文回复','bob','alice')
            cases = [({'to':'missing','text':'secret'},'USER_NOT_FOUND','f2'),
                     ({'to':'alice','text':'secret'},'SELF_TARGET','f2'),
                     ({'to':'BOB','text':'secret'},'USER_NOT_FOUND','f2'),
                     ({'to':'bob','text':''},'BAD_REQUEST',None),
                     ({'to':'bob','text':' \t\n'},'BAD_REQUEST',None),
                     ({'to':'bad name','text':'secret'},'BAD_REQUEST',None),
                     ({'to':'bob','text':42},'BAD_REQUEST',None),
                     ({'to':'bob','text':'secret','sender':'carol'},'BAD_REQUEST',None),
                     ({'to':'bob'},'BAD_REQUEST',None),
                     ({'to':'bob','text':'\x1b[2J'},'BAD_REQUEST',None)]
            for rid,(data,code,feature) in enumerate(cases,2):
                raw_send(alice,'private_send',rid,data)
                reply = receive(alice)
                self.assertEqual((reply.request_id,reply.data['code'],reply.data['fatal'],reply.data['feature']),
                                 (rid,code,False,feature))
            for rid,kind,data,feature in [(12,'broadcast_send',{'text':'no broadcast'},'f1'),
                                          (13,'enhancement_request',{},'f3')]:
                raw_send(alice,kind,rid,data)
                reply=receive(alice)
                self.assertEqual((reply.data['code'],reply.data['feature']),('FEATURE_NOT_IMPLEMENTED',feature))
            self.assert_quiet(alice,bob,carol)
            alice.socket.sendall(private_frame(14,'after errors'))
            self.message(bob,self.result(alice,14),'after errors')

    def test_reconnect_cannot_receive_old_captured_route(self):
        captured, release = threading.Event(), threading.Event()
        def pause_after_lookup(ctx, request):
            result = handle_private(ctx,request)
            if request.text == 'old session only':
                captured.set()
                if not release.wait(3):
                    raise AssertionError('Test did not release captured route.')
            return result
        with running_server(handlers=enabled_handlers(private=pause_after_lookup)) as (server,connect):
            alice,_=connect('alice')
            bob,hello=connect('bob')
            carol,_=connect('carol')
            alice.socket.sendall(private_frame(2,'old session only'))
            try:
                self.assertTrue(captured.wait(2))
                bob.close()
                wait_until(lambda: server.manager.directory.find('bob') is None)
                # Error target during disconnect is tested on a separate sender.
                carol.socket.sendall(private_frame(2,'offline'))
                self.assertEqual(receive(carol).data['code'],'USER_NOT_FOUND')
                new_bob,new_hello=connect('bob')
                self.assertNotEqual(hello.data['session_id'],new_hello.data['session_id'])
            finally:
                release.set()
            self.result(alice,2,queued=0)
            self.assert_quiet(alice,new_bob,carol)
            alice.socket.sendall(private_frame(3,'new session only'))
            self.message(new_bob,self.result(alice,3),'new session only')

    def test_concurrent_senders_preserve_each_sender_order(self):
        with running_server(handlers=enabled_handlers()) as (_,connect):
            alice,_=connect('alice')
            bob,_=connect('bob')
            carol,_=connect('carol')
            barrier=threading.Barrier(3)
            failures=[]
            ids={}
            def produce(channel,name):
                try:
                    barrier.wait(2)
                    for index in range(20):
                        channel.socket.sendall(private_frame(index+2,f'{name}-{index}'))
                        ids[(name,index)]=self.result(channel,index+2)
                except BaseException as exc:
                    failures.append(exc)
            workers=[threading.Thread(target=produce,args=pair) for pair in ((alice,'alice'),(carol,'carol'))]
            for worker in workers:
                worker.start()
            barrier.wait(2)
            messages=[receive(bob) for _ in range(40)]
            for worker in workers:
                worker.join(3)
                self.assertFalse(worker.is_alive())
            self.assertEqual(failures,[])
            for name in ('alice','carol'):
                own=[msg for msg in messages if msg.data['sender']==name]
                self.assertEqual([msg.data['text'] for msg in own],[f'{name}-{i}' for i in range(20)])
                self.assertEqual([msg.data['message_id'] for msg in own],[ids[(name,i)] for i in range(20)])
            self.assertEqual(len({m.data['message_id'] for m in messages}),40)
            self.assertTrue(all(m.type=='chat_message' and m.data['recipient']=='bob' for m in messages))
            self.assert_quiet(alice,bob,carol)

    def test_real_cli_send_receive_errors_and_quit(self):
        with running_server(handlers=enabled_handlers()) as (server,connect):
            bob,_=connect('bob')
            carol,_=connect('carol')
            client=ProcessClient(server.address[1])
            self.addCleanup(client.close)
            client.wait_for('[registered]')
            client.send('@bob '+'x'*300)
            client.wait_for('[queue result]')
            msg=receive(bob)
            self.assertEqual(msg.data['text'],'x'*300)
            bob.socket.sendall(private_frame(2,'reply to real client','alice'))
            self.result(bob,2)
            client.wait_for('[private] bob: reply to real client')
            for command,code in [('@missing hello','USER_NOT_FOUND'),('@alice hello','SELF_TARGET'),('@broken','[usage]')]:
                client.send(command)
                client.wait_for(code)
            client.send('/help')
            client.wait_for('F2=enabled')
            self.assert_quiet(bob,carol)
            self.assertNotIn('[private] alice',''.join(client.lines))
            client.send('/quit')
            self.assertEqual(client.finish(),0)
