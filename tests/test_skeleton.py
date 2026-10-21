import select
import socket
import unittest
import contextlib
import io
import json
import tempfile
import threading
import time
import struct
from pathlib import Path
from unittest.mock import patch

from cse3461_chat.config import ServerConfig
from cse3461_chat.server import ServerRuntime
from cse3461_chat.features import build_handlers
from cse3461_chat.telemetry import EventSink, open_event_sink
from cse3461_chat.transport import FramedConnection
from tests.support import running_server, raw_send, receive, ProcessClient, free_port


class SkeletonTests(unittest.TestCase):
    def test_three_clients_with_one_unregistered(self):
        with running_server() as (server,connect):
            waiting, hello=connect()
            alice,_=connect('alice')
            bob,_=connect('bob')
            self.assertTrue(hello.data['registration_required'])
            self.assertEqual(len(server.manager.directory.others('none')),2)
            for name,state in hello.data['features'].items():
                self.assertEqual(state,dict(implemented=name != 'f3',enabled=False,variant=None))
            for rid,kind,data,feature in [(2,'broadcast_send',{'text':'hello'},'f1'),
                                          (3,'private_send',{'to':'bob','text':'hi'},'f2'),
                                          (4,'enhancement_request',{},'f3')]:
                raw_send(alice,kind,rid,data)
                reply=receive(alice)
                self.assertEqual((reply.type,reply.request_id,reply.data['code'],reply.data['feature']),
                                 ('error',rid,'FEATURE_NOT_IMPLEMENTED' if feature == 'f3' else 'FEATURE_DISABLED',feature))
            self.assertFalse(select.select([bob.socket,waiting.socket,alice.socket],[],[],.05)[0])

    def test_capacity_rejection_before_workers(self):
        with running_server() as (server,connect):
            for _ in range(16):
                connect()
            extra=socket.create_connection(server.address,timeout=1)
            self.addCleanup(extra.close)
            extra.settimeout(1)
            self.assertEqual(extra.recv(1),b'')
            self.assertEqual(len(server.manager.records()),16)
            self.assertTrue(all(s.reader and s.writer for s in server.manager.records()))

    def test_listener_failures(self):
        with socket.socket() as blocker:
            blocker.bind(('127.0.0.1',0))
            blocker.listen()
            output=[]
            server=ServerRuntime(output=output.append)
            code=server.run(ServerConfig(port=blocker.getsockname()[1]),build_handlers(),EventSink('server'))
            self.assertEqual(code,1)
            self.assertFalse(server.ready.is_set())
            self.assertFalse(any('Listening' in line for line in output))

    def test_requested_log_open_failure_starts_no_network(self):
        from cse3461_chat.server import main as server_main
        from cse3461_chat.client import main as client_main
        with tempfile.TemporaryDirectory() as folder, contextlib.redirect_stderr(io.StringIO()):
            for main in (server_main,client_main):
                with patch('socket.socket',side_effect=AssertionError('Network started before log validation')):
                    self.assertEqual(main(['--log-file',folder]),1)

    def test_server_stop_with_blocked_stdin(self):
        with running_server() as (server,connect):
            client=ProcessClient(server.address[1])
            self.addCleanup(client.close)
            client.wait_for('[registered]')
            start=time.monotonic()
            server.stop('server_shutdown')
            self.assertEqual(client.finish(5),0)
            self.assertLess(time.monotonic()-start,5)
            self.assertIn('[bye] server_shutdown',''.join(client.lines))

    def test_multi_session_shutdown_budget(self):
        start=None
        with running_server() as (server,connect):
            for _ in range(16):
                connect()
            start=time.monotonic()
            server.stop('server_shutdown')
        self.assertLess(time.monotonic()-start,5)
        self.assertEqual(server.manager.records(),())

    def test_runtime_logging_failure_stops_process(self):
        with tempfile.TemporaryDirectory() as folder, contextlib.redirect_stderr(io.StringIO()) as errors:
            events=open_event_sink('server',None,str(Path(folder)/'server.jsonl'))
            server=ServerRuntime(output=lambda text:None)
            result=[]
            worker=threading.Thread(target=lambda: result.append(server.run(ServerConfig(port=free_port()),build_handlers(),events)))
            worker.start()
            self.assertTrue(server.ready.wait(3))
            events._stream.close()
            channel=FramedConnection(socket.create_connection(server.address,timeout=1))
            self.addCleanup(channel.close)
            worker.join(5)
            if worker.is_alive():
                server.stop('test_cleanup')
                worker.join(5)
            self.assertEqual(result,[1])
            self.assertFalse(events.valid)
            self.assertIn('invalid',errors.getvalue())

    def test_logs_omit_message_bodies(self):
        with tempfile.TemporaryDirectory() as folder:
            path=Path(folder)/'server.jsonl'
            sink=open_event_sink('server','actual-unit-run',str(path))
            with running_server(events=sink) as (_,connect):
                client,_=connect('alice')
                raw_send(client,'broadcast_send',2,{'text':'DISTINCTIVE_BODY_7ccf'})
                self.assertEqual(receive(client).data['code'],'FEATURE_DISABLED')
            content=path.read_text()
            self.assertNotIn('DISTINCTIVE_BODY_7ccf',content)
            rows=[json.loads(line) for line in content.splitlines()]
            names={row['event'] for row in rows}
            self.assertTrue({'process_started','process_stopped','registration_result','request_received','request_rejected',
                             'outbound_enqueued','frame_write_completed','connection_closed'} <= names)
            self.assertFalse({'route_selected','chat_received'} & names)
            self.assertEqual([r['seq'] for r in rows],list(range(1,len(rows)+1)))

    def test_cli_f1_f2_disabled_and_f3_unimplemented(self):
        with running_server() as (server,connect):
            peer,_=connect('bob')
            client=ProcessClient(server.address[1])
            self.addCleanup(client.close)
            client.wait_for('[registered]')
            for command,feature in [('hello','f1'),('@bob secret','f2'),('/enhance','f3')]:
                client.send(command)
                line=client.wait_for('FEATURE_NOT_IMPLEMENTED' if feature == 'f3' else 'FEATURE_DISABLED')
                self.assertIn('feature='+feature,line)
            client.send('@broken')
            client.wait_for('[usage]')
            client.send('/unknown')
            client.wait_for('[usage]')
            client.send('/all @literal')
            client.wait_for('FEATURE_DISABLED')
            self.assertFalse(select.select([peer.socket],[],[],.05)[0])
            self.assertNotIn('[queue result]',''.join(client.lines))
            client.send('/quit')
            self.assertEqual(client.finish(3),0)

    def test_malformed_peers_and_reset_leave_server_healthy(self):
        bad_payloads=[b'\xff', b'{', b'{"v":1,"v":1}', b'[]', b'{"v":1,"type":"x","request_id":1,"data":{},"extra":1}']
        frames=[struct.pack('!I',len(p))+p for p in bad_payloads]
        frames += [struct.pack('!I',0),struct.pack('!I',65537)]
        with running_server() as (_,connect):
            for index,frame in enumerate(frames):
                c,_=connect()
                c.socket.sendall(frame)
                reply=receive(c)
                self.assertEqual(reply.type,'error')
                self.assertTrue(reply.data['fatal'])
                self.assertIsNone(receive(c))
                good,_=connect('user'+str(index))
                raw_send(good,'disconnect',2,{})
                self.assertEqual(receive(good).type,'bye')
            truncated,_=connect()
            truncated.socket.sendall(b'\x00\x00')
            truncated.socket.shutdown(socket.SHUT_WR)
            self.assertIsNone(receive(truncated))
            reset,_=connect('reset_user')
            reset.socket.setsockopt(socket.SOL_SOCKET,socket.SO_LINGER,struct.pack('ii',1,0))
            reset.socket.close()
            good,_=connect('after_reset')
            self.assertIsNotNone(good)

    def test_registration_deadline_and_retry_on_wire(self):
        with patch('cse3461_chat.config.REGISTRATION_S',.18),running_server(max_clients=1) as (server,connect):
            c,_=connect()
            start=time.monotonic()
            raw_send(c,'register',1,{'username':'bad name'})
            self.assertEqual(receive(c).data['code'],'INVALID_USERNAME')
            reply=receive(c)
            self.assertEqual((reply.data['code'],reply.request_id),('REGISTRATION_TIMEOUT',None))
            self.assertLess(time.monotonic()-start,.8)
            self.assertIsNone(receive(c))
            end=time.monotonic()+1
            while server.manager.records() and time.monotonic()<end:
                time.sleep(.01)
            good,_=connect('alice')
            self.assertIsNotNone(good)
