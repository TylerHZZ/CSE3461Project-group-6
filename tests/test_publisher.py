"""Publication contract with real queues and captured session identities."""
import io
import json
import socket
import time
import unittest

from cse3461_chat.dispatch import Publisher
from cse3461_chat.features.private_chat import handle_private
from cse3461_chat.protocol import (AppError, BroadcastRequest, PrivateRequest, RequestContext,
                                 RoutePlan, PublishResult, capabilities, make_message)
from cse3461_chat.sessions import SessionManager
from cse3461_chat.telemetry import EventSink
from cse3461_chat.transport import FramedConnection


class PublisherTests(unittest.TestCase):
    def setUp(self):
        self.stream=io.StringIO()
        self.manager=SessionManager(16,EventSink('server',stream=self.stream))
        self.records=[]
        self.alice=self.register('alice')
        self.bob=self.register('bob')
        self.carol=self.register('carol')
        self.ctx=RequestContext(self.manager.view(self.alice.session_id),2,123,self.manager.directory)

    def tearDown(self):
        for s in self.records:
            self.manager.close(s.session_id,'test_cleanup')

    def register(self,name):
        a,b=socket.socketpair()
        self.addCleanup(b.close)
        s=self.manager.attach(FramedConnection(a),('127.0.0.1',1234),time.monotonic_ns())
        self.records.append(s)
        reply=make_message('registered',1,dict(session_id=s.session_id,username=name,features=capabilities()))
        self.manager.register(s.session_id,name,reply)
        s.outbound.get_nowait()
        return s

    def test_handler_exact_target_self_missing_and_snapshot(self):
        plan=handle_private(self.ctx,PrivateRequest('bob','secret'))
        self.assertIsInstance(plan,RoutePlan)
        self.assertEqual(plan.recipients,(self.manager.view(self.bob.session_id),))
        for name,code in [('alice','SELF_TARGET'),('missing','USER_NOT_FOUND'),('Bob','USER_NOT_FOUND')]:
            result=handle_private(self.ctx,PrivateRequest(name,'secret'))
            self.assertEqual(result,AppError(code,result.message,False,'f2'))
        self.manager.close(self.bob.session_id,'quit')
        new=self.register('bob')
        self.assertNotEqual(plan.recipients[0].session_id,new.session_id)
        self.assertTrue(self.alice.outbound.empty())
        self.assertTrue(new.outbound.empty())

    def test_private_publication_metadata_and_no_bystander_event(self):
        plan=RoutePlan((self.manager.view(self.bob.session_id),))
        result=Publisher(self.manager).publish(self.ctx,PrivateRequest('bob','DISTINCTIVE_PRIVATE_BODY'),plan)
        self.assertIsInstance(result,PublishResult)
        self.assertEqual((result.status,result.selected_count,result.queued_count,result.not_queued_count),('queued',1,1,0))
        item=self.bob.outbound.get_nowait()
        self.assertEqual(dict(item.message.data),dict(message_id=result.message_id,mode='private',sender='alice',recipient='bob',text='DISTINCTIVE_PRIVATE_BODY'))
        self.assertIsNone(item.message.request_id)
        self.assertEqual((item.meta.origin_session_id,item.meta.origin_request_id,item.meta.feature,item.meta.target_session_id),
                         (self.alice.session_id,2,'f2',self.bob.session_id))
        self.assertGreater(item.meta.enqueued_ns,0)
        self.assertTrue(self.alice.outbound.empty())
        self.assertTrue(self.carol.outbound.empty())
        self.assertNotIn('DISTINCTIVE_PRIVATE_BODY',self.stream.getvalue())
        rows=[json.loads(line) for line in self.stream.getvalue().splitlines()]
        route=[r['fields'] for r in rows if r['event']=='route_selected']
        self.assertEqual(len(route),1)
        self.assertEqual((route[0]['message_id'],route[0]['selected_count']), (result.message_id,1))

    def test_stale_route_reports_not_queued_without_name_relookup(self):
        plan=RoutePlan((self.manager.view(self.bob.session_id),))
        self.manager.close(self.bob.session_id,'quit')
        new=self.register('bob')
        result=Publisher(self.manager).publish(self.ctx,PrivateRequest('bob','old'),plan)
        self.assertEqual((result.status,result.selected_count,result.queued_count,result.not_queued_count),('not_queued',1,0,1))
        self.assertTrue(new.outbound.empty())

    def test_full_queue_closes_target_and_continues_shared_plan(self):
        # Shared publisher supports future F1 plans; this does not enable F1 routing.
        plan=RoutePlan((self.manager.view(self.bob.session_id),self.manager.view(self.carol.session_id)))
        filler=make_message('error',1,dict(code='BAD_REQUEST',message='fixture',fatal=False,feature=None))
        for _ in range(64):
            self.manager.enqueue(self.bob.session_id,filler,None)
        result=Publisher(self.manager).publish(self.ctx,BroadcastRequest('one shared message id'),plan)
        self.assertEqual((result.status,result.selected_count,result.queued_count,result.not_queued_count),('partial',2,1,1))
        self.assertIsNone(self.manager.directory.find('bob'))
        self.assertEqual(self.manager.state(self.bob.session_id),'closed')
        item=self.carol.outbound.get_nowait()
        self.assertEqual((item.message.data['message_id'],item.message.data['recipient']), (result.message_id,None))
        self.assertTrue(self.alice.outbound.empty())

    def test_invalid_plan_never_leaks_private_text(self):
        publisher=Publisher(self.manager)
        for recipients in [(self.manager.view(self.alice.session_id),),
                           (self.manager.view(self.carol.session_id),),
                           (self.manager.view(self.bob.session_id),self.manager.view(self.carol.session_id))]:
            result=publisher.publish(self.ctx,PrivateRequest('bob','secret'),RoutePlan(recipients))
            self.assertEqual((result.code,result.fatal),('INTERNAL_ERROR',True))
        self.assertTrue(all(s.outbound.empty() for s in self.records))

    def test_sender_control_queue_failure_closes_only_sender(self):
        from cse3461_chat.dispatch import Dispatcher
        from cse3461_chat.features import build_handlers
        from cse3461_chat.protocol import Envelope
        filler=make_message('error',1,dict(code='BAD_REQUEST',message='fixture',fatal=False,feature=None))
        for _ in range(64):
            self.manager.enqueue(self.alice.session_id,filler,None)
        dispatcher=Dispatcher(self.manager,build_handlers('f2'),self.manager.events)
        dispatcher.handle(self.alice.session_id,Envelope(1,'private_send',2,dict(to='bob',text='accepted before response fails')),123)
        self.assertEqual(self.manager.state(self.alice.session_id),'closed')
        self.assertIsNone(self.manager.directory.find('alice'))
        self.assertEqual(self.bob.outbound.get_nowait().message.data['text'],'accepted before response fails')
        self.assertIsNotNone(self.manager.directory.find('bob'))
        self.assertIsNotNone(self.manager.directory.find('carol'))
