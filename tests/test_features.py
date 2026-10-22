import unittest
from cse3461_chat.features import build_handlers
from cse3461_chat.features.broadcast import handle_broadcast
from cse3461_chat.features.enhancement import handle_enhancement
from cse3461_chat.protocol import RequestContext, BroadcastRequest, EmptyEnhancementRequest
from cse3461_chat.sessions import SessionView, SessionManager
from cse3461_chat.telemetry import EventSink


class FeatureTests(unittest.TestCase):
    def test_f1_f2_f3_bindings_are_explicit_and_disabled_by_default(self):
        manager = SessionManager(16, EventSink('server'))
        sender = SessionView('old-session', 'alice', ('127.0.0.1', 1))
        ctx = RequestContext(sender, 2, 123, manager.directory)
        result = handle_enhancement(ctx, EmptyEnhancementRequest())
        self.assertEqual((result.code, result.feature, result.fatal), ('STARTUP_CONFIG_ONLY', 'f3', False))
        for enabled in ('none', 'f1', 'f2', 'f3', 'f1,f2', 'f1,f3', 'f2,f3', 'f1,f2,f3'):
            descriptors = {d.id:d for d in build_handlers(enabled).descriptors}
            for f in ('f1', 'f2', 'f3'):
                self.assertTrue(descriptors[f].implemented)
                self.assertEqual(descriptors[f].enabled, f in enabled.split(','))
                self.assertEqual(descriptors[f].variant, 'A' if f == 'f3' else None)

    def test_broadcast_without_other_users_is_no_recipients(self):
        manager = SessionManager(16, EventSink('server'))
        ctx = RequestContext(SessionView('s1', 'alice', ('127.0.0.1', 1)), 2, 123, manager.directory)
        result = handle_broadcast(ctx, BroadcastRequest('hi'))
        self.assertEqual((result.code, result.feature, result.fatal), ('NO_RECIPIENTS', 'f1', False))
