import io
import json
import socket
import time
import unittest
from unittest.mock import patch

from cse3461_chat.client import ClientRuntime, LocalClientError
from cse3461_chat.config import ClientConfig
from cse3461_chat.protocol import make_message, capabilities, Disconnected
from cse3461_chat.telemetry import EventSink
from cse3461_chat.transport import FramedConnection
from tests.support import receive, raw_send, ProcessClient

SID='7e464eee-2f61-4d18-8909-f632214c95ab'


class ClientTests(unittest.TestCase):
    def peer(self, hello=True, registered=False):
        listener=socket.socket(socket.AF_INET,socket.SOCK_STREAM)
        listener.bind(('127.0.0.1',0))
        listener.listen()
        self.addCleanup(listener.close)
        client=ClientRuntime()
        info=client.connect(ClientConfig(port=listener.getsockname()[1]),EventSink('client'))
        self.addCleanup(client.close,'test_end')
        peer=FramedConnection(listener.accept()[0])
        self.addCleanup(peer.close)
        if hello:
            peer.write(make_message('hello',None,dict(session_id=SID,registration_required=True,max_frame_bytes=65536,
                max_text_bytes=4096,registration_timeout_s=30,features=capabilities())))
            self.assertEqual(client.next_event(1).type,'hello')
        if registered:
            rid=client.send('register',{'username':'alice'})
            self.assertEqual(receive(peer).request_id,rid)
            peer.write(make_message('registered',rid,dict(session_id=SID,username='alice',features=capabilities())))
            self.assertEqual(client.next_event(1).type,'registered')
        return client,peer,info

    def test_chat_receipt_log_uses_receiver_timestamp_and_omits_body(self):
        client, peer, _ = self.peer(registered=True)
        stream = io.StringIO()
        client.events = EventSink('client', stream=stream)
        mid = '98311d34-a0c9-4417-aeee-2b58a840c001'
        peer.write(make_message('chat_message', None, dict(message_id=mid, mode='private',
            sender='bob', recipient='alice', text='秘密正文')))
        self.assertEqual(client.next_event(1).type, 'chat_message')
        rows = [json.loads(line) for line in stream.getvalue().splitlines()]
        chats = [r['fields'] for r in rows if r['event']=='chat_received']
        self.assertEqual(len(chats), 1)
        self.assertEqual(chats[0]['message_id'], mid)
        self.assertEqual(chats[0]['receiver_session_id'], SID)
        self.assertEqual(chats[0]['text_bytes'], 12)
        self.assertEqual(chats[0]['received_ns'], client.channel.last_receive.received_ns)
        self.assertNotIn('秘密正文', stream.getvalue())

    def test_client_handshake_and_request_state(self):
        client,peer,info=self.peer()
        self.assertEqual(client.state,'AWAITING_REGISTRATION')
        self.assertEqual(info.local_address,client.channel.socket.getsockname())
        self.assertEqual(info.server_address,client.channel.socket.getpeername())
        with self.assertRaises(LocalClientError):
            client.send('broadcast_send',{'text':'hi'})
        rid=client.send('register',{'username':'alice'})
        self.assertEqual(receive(peer).request_id,1)
        peer.write(make_message('error',rid,dict(code='USERNAME_TAKEN',message='Taken',fatal=False,feature=None)))
        client.next_event(1)
        self.assertEqual(client.state,'AWAITING_REGISTRATION')
        rid=client.send('register',{'username':'bob'})
        self.assertEqual(receive(peer).request_id,2)
        peer.write(make_message('registered',rid,dict(session_id=SID,username='bob',features=capabilities())))
        client.next_event(1)
        self.assertEqual((client.state,client.username),('REGISTERED','bob'))
        for _ in range(32):
            client.send('broadcast_send',{'text':'hi'})
        with self.assertRaises(LocalClientError):
            client.send('broadcast_send',{'text':'extra'})
        for rid in range(3,35):
            self.assertEqual(receive(peer).request_id,rid)
        peer.write(make_message('error',3,dict(code='FEATURE_NOT_IMPLEMENTED',message='Unavailable',fatal=False,feature='f1')))
        client.next_event(1)
        self.assertEqual(client.state,'REGISTERED')

    def test_hello_deadline(self):
        with patch('cse3461_chat.config.HELLO_S',.03):
            client,peer,_=self.peer(hello=False)
            time.sleep(.04)
            result=client.next_event(.1)
            self.assertIsInstance(result,Disconnected)
            self.assertEqual(result.reason,'hello_timeout')

    def test_registration_reply_while_closing_preserves_graceful_quit(self):
        client,peer,_=self.peer()
        registration=client.send('register',{'username':'alice'})
        quit_id=client.send('disconnect',{})
        self.assertEqual(receive(peer).request_id,registration)
        self.assertEqual(receive(peer).request_id,quit_id)
        peer.write(make_message('registered',registration,dict(session_id=SID,username='alice',features=capabilities())))
        self.assertEqual(client.next_event(1).type,'registered')
        self.assertEqual((client.state,client.username),('CLOSING','alice'))
        self.assertEqual(set(client.pending),{quit_id})
        with self.assertRaises(LocalClientError):
            client.send('broadcast_send',{'text':'must remain closed to new work'})
        peer.write(make_message('bye',quit_id,{'reason':'client_request'}))
        self.assertEqual(client.next_event(1).type,'bye')
        self.assertEqual((client.state,client.close_reason),('CLOSED','client_request'))
        self.assertEqual(client.unknown_count,0)

    def test_timeout_and_late_response(self):
        client,peer,_=self.peer(registered=True)
        with patch('cse3461_chat.config.REQUEST_S',.03):
            rid=client.send('broadcast_send',{'text':'hi'})
            receive(peer)
            time.sleep(.04)
            self.assertIsNone(client.next_event(0))
            self.assertEqual(len(client.pending),0)
            self.assertTrue(any('outcome unknown' in s for s in client.drain_notices()))
            peer.write(make_message('error',rid,dict(code='FEATURE_NOT_IMPLEMENTED',message='Unavailable',fatal=False,feature='f1')))
            client.next_event(1)
            self.assertEqual(client.state,'REGISTERED')
            self.assertTrue(any('Late/unmatched' in s for s in client.drain_notices()))
        other,other_peer,_=self.peer()
        with patch('cse3461_chat.config.REQUEST_S',.03):
            other.send('register',{'username':'carol'})
            receive(other_peer)
            time.sleep(.04)
            self.assertIsInstance(other.next_event(0),Disconnected)
            self.assertEqual(other.state,'CLOSED')

    def test_terminal_failure_survives_full_event_queue(self):
        client,peer,_=self.peer(registered=True)
        rid=client.send('broadcast_send',{'text':'hi'})
        receive(peer)
        for _ in range(65):
            try:
                peer.write(make_message('error',rid,dict(code='FEATURE_NOT_IMPLEMENTED',message='Unavailable',fatal=False,feature='f1')))
            except OSError:
                break
        self.assertTrue(client.terminal.wait(2))
        result=client.next_event(0)
        self.assertIsInstance(result,Disconnected)
        self.assertEqual(result.reason,'event_queue_overflow')
        self.assertEqual(client.state,'CLOSED')
        self.assertTrue(any('outcome unknown' in s for s in client.drain_notices()))

    def test_invalid_server_traffic_closes_locally(self):
        client,peer,_=self.peer()
        raw_send(peer,'register',1,{'username':'bad-direction'})
        self.assertTrue(client.terminal.wait(2))
        self.assertIsInstance(client.next_event(0),Disconnected)
        self.assertIsNone(receive(peer))


class ClientQuitTests(unittest.TestCase):
    def cli_peer(self):
        listener=socket.socket(socket.AF_INET,socket.SOCK_STREAM)
        listener.bind(('127.0.0.1',0))
        listener.listen()
        self.addCleanup(listener.close)
        client=ProcessClient(listener.getsockname()[1])
        self.addCleanup(client.close)
        listener.settimeout(3)
        peer=FramedConnection(listener.accept()[0])
        self.addCleanup(peer.close)
        client.wait_for('Connected:')
        return client,peer

    def test_quit_before_hello_closes_promptly(self):
        client,peer=self.cli_peer()
        client.send('/quit')
        self.assertEqual(client.finish(1),0)

    def test_quit_and_eof_during_registration_exit_cleanly(self):
        for use_eof in (False,True):
            with self.subTest(use_eof=use_eof):
                client,peer=self.cli_peer()
                peer.write(make_message('hello',None,dict(session_id=SID,registration_required=True,max_frame_bytes=65536,
                    max_text_bytes=4096,registration_timeout_s=30,features=capabilities())))
                registration=receive(peer).request_id
                if use_eof:
                    client.process.stdin.close()
                else:
                    client.send('/quit')
                disconnect=receive(peer)
                self.assertEqual(disconnect.type,'disconnect')
                peer.write(make_message('registered',registration,dict(session_id=SID,username='alice',features=capabilities())))
                peer.write(make_message('bye',disconnect.request_id,{'reason':'client_request'}))
                self.assertEqual(client.finish(2),0)
                output=''.join(client.lines)
                self.assertIn('[bye] client_request',output)
                self.assertNotIn('outcome unknown',output)

    def test_quit_with_full_pending_table(self):
        client,peer=self.cli_peer()
        peer.write(make_message('hello',None,dict(session_id=SID,registration_required=True,max_frame_bytes=65536,
            max_text_bytes=4096,registration_timeout_s=30,features=capabilities())))
        rid=receive(peer).request_id
        peer.write(make_message('registered',rid,dict(session_id=SID,username='alice',features=capabilities())))
        client.wait_for('[registered]')
        for _ in range(32):
            client.send('waiting')
        for _ in range(32):
            receive(peer,3)
        client.send('/quit')
        self.assertEqual(client.finish(1),0)
        self.assertIn('outcome unknown',''.join(client.lines))
