import unittest
from cse3461_chat.features import build_handlers
from cse3461_chat.features.broadcast import handle_broadcast
from cse3461_chat.features.enhancement import handle_enhancement
from cse3461_chat.protocol import RequestContext, BroadcastRequest, EmptyEnhancementRequest
from cse3461_chat.sessions import SessionView, SessionManager
from cse3461_chat.telemetry import EventSink


class FeatureTests(unittest.TestCase):
    def test_f1_f3_stubs_remain_unavailable_and_f2_binding_is_explicit(self):
        manager = SessionManager(16, EventSink('server'))
        sender = SessionView('old-session', 'alice', ('127.0.0.1', 1))
        ctx = RequestContext(sender, 2, 123, manager.directory)
        for handler, request, feature in [(handle_broadcast, BroadcastRequest('hi'), 'f1'),
                                           (handle_enhancement, EmptyEnhancementRequest(), 'f3')]:
            result = handler(ctx, request)
            self.assertEqual((result.code, result.feature, result.fatal), ('FEATURE_NOT_IMPLEMENTED', feature, False))
        for enabled in ('none', 'f2'):
            descriptors = {d.id:d for d in build_handlers(enabled).descriptors}
            self.assertTrue(descriptors['f2'].implemented)
            self.assertEqual(descriptors['f2'].enabled, enabled == 'f2')
            self.assertTrue(all(not descriptors[f].implemented and not descriptors[f].enabled
                                for f in ('f1', 'f3')))
            self.assertTrue(all(d.variant is None for d in descriptors.values()))
