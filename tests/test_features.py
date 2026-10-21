import unittest
from cse3461_chat.features import build_handlers
from cse3461_chat.features.broadcast import handle_broadcast
from cse3461_chat.features.enhancement import handle_enhancement
from cse3461_chat.protocol import RequestContext, BroadcastRequest, EmptyEnhancementRequest
from cse3461_chat.sessions import SessionView, SessionManager
from cse3461_chat.telemetry import EventSink


class FeatureTests(unittest.TestCase):
    def test_f1_stub_and_explicit_f2_f3_bindings(self):
        manager = SessionManager(16, EventSink('server'))
        sender = SessionView('old-session', 'alice', ('127.0.0.1', 1))
        ctx = RequestContext(sender, 2, 123, manager.directory)
        for handler, request, feature in [(handle_broadcast, BroadcastRequest('hi'), 'f1'),
                                           (handle_enhancement, EmptyEnhancementRequest(), 'f3')]:
            result = handler(ctx, request)
            self.assertEqual((result.code, result.feature, result.fatal), ('STARTUP_CONFIG_ONLY' if feature == 'f3' else 'FEATURE_NOT_IMPLEMENTED', feature, False))
        for enabled in ('none', 'f2'):
            descriptors = {d.id:d for d in build_handlers(enabled).descriptors}
            self.assertTrue(descriptors['f2'].implemented)
            self.assertEqual(descriptors['f2'].enabled, enabled == 'f2')
            self.assertTrue(all(not descriptors[f].implemented and not descriptors[f].enabled
                                for f in ('f1',)))
            self.assertTrue(descriptors['f3'].implemented)
            self.assertFalse(descriptors['f3'].enabled)
            self.assertEqual(descriptors['f3'].variant, 'A')
            self.assertIsNone(descriptors['f2'].variant)
