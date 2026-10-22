import select
import json
import tempfile
import unittest
from dataclasses import replace
from pathlib import Path

from cse3461_chat.features import build_handlers
from cse3461_chat.protocol import FeatureDescriptor
from cse3461_chat.telemetry import open_event_sink
from tests.support import running_server, raw_send, receive


class DispatchTests(unittest.TestCase):
    def test_rejected_registration_logs_only_valid_username_metadata(self):
        with tempfile.TemporaryDirectory() as folder:
            path=Path(folder)/'server.jsonl'
            sink=open_event_sink('server','malformed-registration',str(path))
            with running_server(events=sink) as (_,connect):
                client,_=connect()
                for rid,username in enumerate(({'text':'PRIVATE_BODY'},'INVALID_BODY_'*1000),1):
                    raw_send(client,'register',rid,{'username':username})
                    self.assertEqual(receive(client).data['code'],'INVALID_USERNAME')
                raw_send(client,'register',3,{'username':'alice','text':'EXTRA_BODY'})
                self.assertEqual(receive(client).data['code'],'BAD_REQUEST')
                raw_send(client,'register',4,{'username':'alice'})
                self.assertEqual(receive(client).type,'registered')
            content=path.read_text()
            for marker in ('PRIVATE_BODY','INVALID_BODY_','EXTRA_BODY'):
                self.assertNotIn(marker,content)
            rows=[json.loads(line) for line in content.splitlines()]
            rejected=[row['fields'] for row in rows if row['event']=='registration_result' and not row['fields']['accepted']]
            self.assertEqual([row['requested_username'] for row in rejected],[None,None,'alice'])
            self.assertEqual([row['error_code'] for row in rejected],['INVALID_USERNAME','INVALID_USERNAME','BAD_REQUEST'])

    def test_dispatch_validation_order(self):
        with running_server() as (_, connect):
            c, _ = connect()
            cases = [('broadcast_send', {'text':'hi'}, 'NOT_REGISTERED'),
                     ('future', {}, 'UNKNOWN_TYPE'), ('error', {}, 'WRONG_DIRECTION'),
                     ('register', {'username':'bad name'}, 'INVALID_USERNAME')]
            for rid, (kind,data,code) in enumerate(cases, 1):
                raw_send(c,kind,rid,data)
                result=receive(c)
                self.assertEqual((result.request_id,result.data['code']), (rid,code))
            raw_send(c,'register',5,{'username':'alice'})
            self.assertEqual(receive(c).type,'registered')
            raw_send(c,'register',6,{'username':'bob'})
            self.assertEqual(receive(c).data['code'],'ALREADY_REGISTERED')
            raw_send(c,'disconnect',7,{},version=2)
            self.assertEqual(receive(c).data['code'],'UNSUPPORTED_VERSION')
            self.assertIsNone(receive(c))

    def test_rejected_body_consumes_id(self):
        with running_server() as (_,connect):
            c,_=connect('alice')
            raw_send(c,'broadcast_send',2,{'text':''})
            self.assertEqual(receive(c).data['code'],'BAD_REQUEST')
            raw_send(c,'broadcast_send',2,{'text':'valid'})
            reply=receive(c)
            self.assertEqual((reply.data['code'],reply.data['fatal'],reply.request_id), ('BAD_REQUEST_ID',True,None))
            self.assertIsNone(receive(c))

    def test_spoofed_sender_never_dispatches(self):
        calls=[]
        def forbidden(*args):
            calls.append(args)
            raise AssertionError('Business handler invoked')
        handlers=replace(build_handlers(), broadcast=forbidden)
        with running_server(handlers=handlers) as (_,connect):
            c,_=connect('alice')
            peer,_=connect('bob')
            raw_send(c,'broadcast_send',2,{'text':'hi','sender':'bob'})
            self.assertEqual(receive(c).data['code'],'BAD_REQUEST')
            raw_send(c,'broadcast_send',3,{'text':'hi'})
            self.assertEqual(receive(c).data['code'],'FEATURE_DISABLED')
            self.assertEqual(calls,[])
            self.assertFalse(select.select([peer.socket],[],[],.05)[0])

    def test_disabled_gate_is_distinct(self):
        handlers=replace(build_handlers(), descriptors=(FeatureDescriptor('f1',True,False),FeatureDescriptor('f2'),FeatureDescriptor('f3')))
        with running_server(handlers=handlers) as (_,connect):
            c,_=connect('alice')
            raw_send(c,'broadcast_send',2,{'text':'hi'})
            self.assertEqual(receive(c).data['code'],'FEATURE_DISABLED')

    def test_invalid_request_ids(self):
        for rid in [None,True,0,-1,9007199254740992]:
            with self.subTest(rid=rid),running_server() as (_,connect):
                c,_=connect()
                raw_send(c,'register',rid,{'username':'alice'})
                reply=receive(c)
                self.assertEqual((reply.data['code'],reply.request_id), ('BAD_REQUEST_ID',None))
