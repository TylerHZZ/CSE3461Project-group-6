import json
import unittest
from uuid import UUID

from cse3461_chat.protocol import (
    Envelope, WireMessage, ProtocolError, AppError, decode_payload,
    validate_message, capabilities,
)

SID = '7e464eee-2f61-4d18-8909-f632214c95ab'


class ProtocolTests(unittest.TestCase):
    def validate(self, kind, data, direction='c2s', rid=1):
        return validate_message(Envelope(1, kind, rid, data), direction)

    def test_strict_envelope_and_json(self):
        for raw in [b'\xff', b'{', b'{"v":1,"v":1}', b'{"x":NaN}',
                    b'{"x":Infinity}', b'{"x":"\\ud800"}']:
            with self.subTest(raw=raw):
                self.assertEqual(decode_payload(raw).code, 'INVALID_JSON')
        for raw in [b'[]', b'{}', b'{"v":true,"type":"x","request_id":1,"data":{}}',
                    b'{"v":1,"type":"x","request_id":1,"data":{},"extra":1}']:
            self.assertEqual(decode_payload(raw).code, 'INVALID_ENVELOPE')
        self.assertEqual(decode_payload(b'{"v":1,"type":"x","request_id":true,"data":{}}').code,
                         'BAD_REQUEST_ID')
        env = decode_payload(b'{"v":99,"type":"future","request_id":2,"data":{"x":1}}')
        self.assertIsInstance(env, Envelope)
        self.assertEqual((env.v, env.type, env.data), (99, 'future', {'x': 1}))

    def test_message_schemas_and_direction(self):
        cases = {
            'register': {'username': 'Alice_1'}, 'broadcast_send': {'text': 'hello'},
            'private_send': {'to': 'bob', 'text': 'hello'}, 'enhancement_request': {},
            'disconnect': {},
        }
        for kind, data in cases.items():
            with self.subTest(kind=kind):
                self.assertIsInstance(self.validate(kind, data), WireMessage)
                self.assertEqual(self.validate(kind, data, 's2c').code, 'WRONG_DIRECTION')
                self.assertEqual(self.validate(kind, {**data, 'sender': 'spoof'}).code, 'BAD_REQUEST')
        self.assertEqual(self.validate('future', {}).code, 'UNKNOWN_TYPE')
        self.assertEqual(self.validate('register', {'username': ''}).code, 'INVALID_USERNAME')
        for name in ['a', 'a'*24]:
            self.assertIsInstance(self.validate('register', {'username': name}), WireMessage)
        for name in ['a'*25, ' alice', 'é', 'bob\n']:
            self.assertEqual(self.validate('register', {'username': name}).code, 'INVALID_USERNAME')
        for text in ['a', 'a'*4096, 'é'*2048, 'hi\tthere\n']:
            self.assertEqual(self.validate('broadcast_send', {'text': text}).data['text'], text)
        for text in ['', ' \t\n', 'a'*4097, 'é'*2049, 'hi\x1b[2J', 'hi\u202e']:
            self.assertEqual(self.validate('broadcast_send', {'text': text}).code, 'BAD_REQUEST')

    def test_server_schemas_and_immutable_payload(self):
        rows = [
            ('hello', None, dict(session_id=SID, registration_required=True, max_frame_bytes=65536,
                                max_text_bytes=4096, registration_timeout_s=30, features=capabilities())),
            ('registered', 1, dict(session_id=SID, username='alice', features=capabilities())),
            ('chat_message', None, dict(message_id=SID, mode='broadcast', sender='alice', recipient=None, text='hi')),
            ('send_result', 2, dict(message_id=SID, status='partial', selected_count=2, queued_count=1, not_queued_count=1)),
            ('bye', None, {'reason': 'server_shutdown'}),
            ('error', 2, dict(code='FEATURE_NOT_IMPLEMENTED', message='Unavailable', fatal=False, feature='f1')),
        ]
        for kind, rid, data in rows:
            with self.subTest(kind=kind):
                msg = self.validate(kind, data, 's2c', rid)
                self.assertIsInstance(msg, WireMessage)
                with self.assertRaises(TypeError):
                    msg.data['new'] = 1
                self.assertEqual(self.validate(kind, data, 'c2s', rid).code, 'WRONG_DIRECTION')
        data = rows[0][2]
        msg = self.validate('hello', data, 's2c', None)
        data['features']['f1']['enabled'] = True
        self.assertFalse(msg.data['features']['f1']['enabled'])
        bad = dict(rows[3][2], queued_count=True)
        self.assertEqual(self.validate('send_result', bad, 's2c', 2).code, 'BAD_REQUEST')
        bad = dict(rows[3][2], queued_count=3)
        self.assertEqual(self.validate('send_result', bad, 's2c', 2).code, 'BAD_REQUEST')
        self.assertEqual(self.validate('hello', rows[0][2], 's2c', 1).code, 'BAD_REQUEST')


if __name__ == '__main__':
    unittest.main()
