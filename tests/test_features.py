import unittest
from cse3461_chat.features import build_handlers
from cse3461_chat.features.broadcast import handle_broadcast
from cse3461_chat.features.private_chat import handle_private
from cse3461_chat.features.enhancement import handle_enhancement
from cse3461_chat.dispatch import Publisher
from cse3461_chat.protocol import RequestContext, BroadcastRequest, PrivateRequest, EmptyEnhancementRequest, RoutePlan
from cse3461_chat.sessions import SessionView, SessionManager
from cse3461_chat.telemetry import EventSink


class FeatureTests(unittest.TestCase):
    def test_feature_stubs_and_publisher_are_unavailable(self):
        manager = SessionManager(16, EventSink('server'))
        sender = SessionView('old-session', 'alice', ('127.0.0.1', 1))
        target = SessionView('target-session', 'bob', ('127.0.0.1', 2))
        ctx = RequestContext(sender, 2, 123, manager.directory)
        for handler, request, feature in [(handle_broadcast, BroadcastRequest('hi'), 'f1'),
                                           (handle_private, PrivateRequest('bob','hi'), 'f2'),
                                           (handle_enhancement, EmptyEnhancementRequest(), 'f3')]:
            result = handler(ctx, request)
            self.assertEqual((result.code, result.feature, result.fatal), ('FEATURE_NOT_IMPLEMENTED', feature, False))
        for request, feature in [(BroadcastRequest('hi'),'f1'),(PrivateRequest('bob','hi'),'f2')]:
            result = Publisher().publish(ctx, request, RoutePlan((target,)))
            self.assertEqual((result.code,result.feature), ('FEATURE_NOT_IMPLEMENTED',feature))
        self.assertTrue(all(not d.implemented and not d.enabled and d.variant is None for d in build_handlers().descriptors))
