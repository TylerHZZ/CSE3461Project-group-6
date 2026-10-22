"""F1 wire behavior: every other registered user receives one copy; the sender gets no echo."""
import select
import unittest

from cse3461_chat.features import build_handlers
from tests.support import running_server, raw_send, receive, ProcessClient


class BroadcastWireTests(unittest.TestCase):
    def assert_quiet(self, *channels):
        self.assertFalse(select.select([c.socket for c in channels], [], [], .1)[0],
                         'Unexpected notification, echo, error, or duplicate frame.')

    def test_broadcast_reaches_all_others_without_echo(self):
        with running_server(handlers=build_handlers('f1')) as (_, connect):
            waiting, _ = connect()
            alice, _ = connect('alice')
            bob, _ = connect('bob')
            carol, _ = connect('carol')
            raw_send(alice, 'broadcast_send', 2, {'text': 'Hello everyone'})
            reply = receive(alice)
            self.assertEqual((reply.type, reply.request_id), ('send_result', 2))
            self.assertEqual((reply.data['status'], reply.data['selected_count'],
                              reply.data['queued_count'], reply.data['not_queued_count']), ('queued', 2, 2, 0))
            for recipient in (bob, carol):
                msg = receive(recipient)
                self.assertEqual((msg.type, msg.request_id), ('chat_message', None))
                self.assertEqual(dict(msg.data), dict(message_id=reply.data['message_id'], mode='broadcast',
                                                      sender='alice', recipient=None, text='Hello everyone'))
            self.assert_quiet(waiting, alice, bob, carol)

    def test_no_recipients_and_disconnected_users_are_skipped(self):
        with running_server(handlers=build_handlers('f1')) as (_, connect):
            alice, _ = connect('alice')
            raw_send(alice, 'broadcast_send', 2, {'text': 'anyone?'})
            reply = receive(alice)
            self.assertEqual((reply.type, reply.request_id, reply.data['code'], reply.data['fatal'], reply.data['feature']),
                             ('error', 2, 'NO_RECIPIENTS', False, 'f1'))
            bob, _ = connect('bob')
            raw_send(bob, 'disconnect', 2, {})
            self.assertEqual(receive(bob).type, 'bye')
            raw_send(alice, 'broadcast_send', 3, {'text': 'still anyone?'})
            self.assertEqual(receive(alice).data['code'], 'NO_RECIPIENTS')

    def test_cli_broadcast_between_real_clients(self):
        with running_server(handlers=build_handlers('f1,f2')) as (server, _):
            clients = {name: ProcessClient(server.address[1], name) for name in ('alice', 'bob', 'carol')}
            for client in clients.values():
                self.addCleanup(client.close)
                client.wait_for('[registered]')
            clients['alice'].send('Hello from Alice')
            clients['alice'].wait_for('[queue result]')
            for name in ('bob', 'carol'):
                clients[name].wait_for('[broadcast] alice: Hello from Alice')
            self.assertNotIn('[broadcast]', ''.join(clients['alice'].lines))
            for client in clients.values():
                client.send('/quit')
                self.assertEqual(client.finish(3), 0)
