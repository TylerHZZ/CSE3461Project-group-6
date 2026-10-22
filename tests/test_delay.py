"""F3 policy/config regressions; assertions catch invalid config and wrong sampling."""
import contextlib
import io
import threading
import unittest
from cse3461_chat import config
from cse3461_chat.features import build_handlers, enhancement


class DelayPolicyTests(unittest.TestCase):
    def policy(self, mode='jitter', delay=20, jitter=15, seed=7, username='bob'):
        self.assertTrue(hasattr(enhancement, 'DelayPolicy'), 'F3 delay policy is missing')
        return enhancement.DelayPolicy(mode, delay, jitter, seed, username)

    def test_seed_repeats_per_recipient_without_shared_draw_order(self):
        a, b = self.policy(), self.policy()
        other = self.policy(username='carol')
        values = []
        for _ in range(50):
            values.append(a.select_ms())
            other.select_ms()
        self.assertEqual(values, [b.select_ms() for _ in range(50)])
        self.assertTrue(all(5 <= x <= 35 for x in values))
        self.assertGreater(len(set(values)), 40)
        self.assertNotEqual(values, [self.policy(username='carol').select_ms()]*50)
        self.assertNotEqual(values[0], self.policy(seed=8).select_ms())

    def test_fixed_zero_off_and_cancelled_wait(self):
        for mode, delay in [('off', 0), ('fixed', 0), ('fixed', 20)]:
            policy = self.policy(mode, delay, 0)
            self.assertEqual(policy.select_ms(), delay)
        policy = self.policy('fixed', 1000, 0)
        cancel = threading.Event()
        timer = threading.Timer(.03, cancel.set)
        timer.start()
        result = policy.before_chat_write(cancel)
        timer.join()
        self.assertTrue(result.cancelled)
        self.assertLess((result.ended_ns-result.started_ns)/1e9, .5)
        self.assertEqual(result.selected_ms, 1000)
        self.assertGreaterEqual(result.ended_ns, result.started_ns)

    def test_config_enablement_zero_and_capabilities(self):
        with contextlib.redirect_stderr(io.StringIO()):
            try:
                cfg = config.parse_server_args(['--features','f2,f3','--delay-mode','fixed'])
            except SystemExit:
                self.fail('F3 configuration is not supported')
        self.assertEqual(cfg.delay_ms, 0)
        descriptors = {d.id:d for d in build_handlers(cfg.features).descriptors}
        self.assertTrue(descriptors['f3'].implemented and descriptors['f3'].enabled)
        self.assertEqual(descriptors['f3'].variant, 'A')
        self.assertTrue(descriptors['f1'].implemented)
        self.assertFalse(descriptors['f1'].enabled)
        self.assertFalse({d.id:d for d in build_handlers().descriptors}['f3'].enabled)

    def test_invalid_configs_fail_before_listening(self):
        # Removing finite/range/mode validation must fail these literal cases.
        self.assertTrue(hasattr(config.ServerConfig(), 'delay_mode'), 'F3 fields missing')
        cases = [dict(delay_ms=-1), dict(delay_ms=float('nan')), dict(delay_ms=float('inf')),
                 dict(delay_ms=True), dict(jitter_ms=-1), dict(delay_seed=True),
                 dict(delay_seed=-1), dict(delay_seed=2**32), dict(delay_mode='random'),
                 dict(delay_mode='fixed'), dict(features='f3'),
                 dict(features='f2,f3', delay_mode='fixed', jitter_ms=1),
                 dict(features='f3', delay_mode='jitter', delay_ms=10, jitter_ms=11),
                 dict(features='f3', delay_mode='jitter', delay_ms=900, jitter_ms=101)]
        for fields in cases:
            with self.subTest(fields=fields), self.assertRaises(ValueError):
                config.validate_config(config.ServerConfig(**fields))
        config.validate_config(config.ServerConfig(features='f3', delay_mode='jitter', delay_ms=500, jitter_ms=500))
