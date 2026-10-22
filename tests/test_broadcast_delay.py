"""F1 through the actual F3 per-recipient writer and bounded queue path."""
import io
import json
import select
import time
import unittest

from cse3461_chat.config import ServerConfig
from cse3461_chat.telemetry import EventSink
from tests.support import running_server, free_port, raw_send, receive
from tests.test_private import wait_until


class KeepStream(io.StringIO):
    def close(self): pass


class BroadcastDelayTests(unittest.TestCase):
    def setup_server(self, delay=30, mode='fixed', jitter=0, features='f1,f2,f3'):
        self.stream = KeepStream()
        cfg = ServerConfig(port=free_port(), features=features, delay_mode=mode,
                           delay_ms=delay, jitter_ms=jitter, delay_seed=20261021)
        return running_server(server_config=cfg, events=EventSink('server', stream=self.stream))

    def rows(self, event):
        return [r['fields'] for line in self.stream.getvalue().splitlines()
                if (r:=json.loads(line))['event']==event]

    def broadcast(self, alice, rid):
        raw_send(alice, 'broadcast_send', rid, dict(text=f'm{rid}'))
        reply = receive(alice)
        self.assertEqual(reply.type, 'send_result')
        return reply

    def test_f1_only_with_delay_off_fixed_jitter_and_zero_preserves_recipient_fifo(self):
        # Detects a hook applied only to private chat or shared RNG/writer streams.
        for mode, delay, jitter in [('off',0,0), ('fixed',20,0), ('jitter',20,15), ('fixed',0,0)]:
            with self.subTest(mode=mode, delay=delay):
                with self.setup_server(delay, mode, jitter, 'f1' if mode=='off' else 'f1,f3') as (_, connect):
                    alice, _=connect('alice'); bob, bh=connect('bob'); carol, ch=connect('carol')
                    ids=[self.broadcast(alice,rid).data['message_id'] for rid in range(2,10)]
                    for channel in (bob,carol):
                        messages=[receive(channel) for _ in ids]
                        self.assertEqual([m.data['message_id'] for m in messages],ids)
                        self.assertEqual([m.data['text'] for m in messages],[f'm{rid}' for rid in range(2,10)])
                    self.assertFalse(select.select([alice.socket],[],[],.03)[0])
                    wait_until(lambda:len(self.rows('chat_delay_completed'))==16)
                    streams=[]
                    for hello in (bh,ch):
                        rows=[r for r in self.rows('chat_delay_completed') if r['target_session_id']==hello.data['session_id']]
                        self.assertEqual([r['message_id'] for r in rows],ids)
                        self.assertTrue(all(r['feature']=='f1' and not r['cancelled'] for r in rows))
                        values=[r['selected_ms'] for r in rows]; streams.append(values)
                        self.assertTrue(all(delay-jitter <= v <= delay+jitter for v in values))
                        self.assertTrue(all(r['actual_wait_ns']==r['wait_ended_ns']-r['wait_started_ns'] for r in rows))
                    if mode=='jitter': self.assertNotEqual(*streams)

    def test_f3_full_private_queue_does_not_block_healthy_broadcast_recipient(self):
        # Fill Bob's actual 64-frame queue while a real F3 wait is in flight.
        with self.setup_server(1000) as (server,connect):
            alice,_=connect('alice'); bob,bh=connect('bob'); carol,_=connect('carol')
            for rid in range(2,67):
                raw_send(alice,'private_send',rid,dict(to='bob',text=f'queued {rid}'))
                self.assertEqual(receive(alice).data['status'],'queued')
                if rid==2: wait_until(lambda:self.rows('chat_dequeued'))
            reply=self.broadcast(alice,67)
            self.assertEqual(tuple(reply.data[k] for k in ('status','selected_count','queued_count','not_queued_count')),('partial',2,1,1))
            self.assertIsNone(server.manager.directory.find('bob'))
            self.assertEqual(receive(carol).data['message_id'],reply.data['message_id'])
            self.assertIsNone(receive(bob))
            wait_until(lambda:server.manager.discarded==65)
            cancelled=[r for r in self.rows('chat_delay_completed') if r['cancelled']]
            self.assertEqual([r['target_session_id'] for r in cancelled],[bh.data['session_id']])

    def test_broadcast_disconnect_cancels_only_departed_recipient_and_no_replay(self):
        with self.setup_server(300) as (server,connect):
            alice,_=connect('alice'); bob,bh=connect('bob'); carol,ch=connect('carol')
            mid=self.broadcast(alice,2).data['message_id']
            wait_until(lambda:len(self.rows('chat_dequeued'))==2)
            bob.close(); wait_until(lambda:server.manager.directory.find('bob') is None)
            replacement,new=connect('bob')
            self.assertNotEqual(bh.data['session_id'],new.data['session_id'])
            self.assertEqual(receive(carol).data['message_id'],mid)
            self.assertFalse(select.select([replacement.socket,alice.socket],[],[],.04)[0])
            wait_until(lambda:len(self.rows('chat_delay_completed'))==2)
            rows={r['target_session_id']:r for r in self.rows('chat_delay_completed')}
            self.assertTrue(rows[bh.data['session_id']]['cancelled'])
            self.assertFalse(rows[ch.data['session_id']]['cancelled'])
            self.assertEqual(server.manager.discarded,1)

    def test_shutdown_cancels_both_broadcast_waits_and_drains_bye(self):
        with self.setup_server(1000) as (server,connect):
            alice,_=connect('alice'); bob,_=connect('bob'); carol,_=connect('carol')
            self.broadcast(alice,2)
            wait_until(lambda:len(self.rows('chat_dequeued'))==2)
            start=time.monotonic(); server.stop('server_shutdown')
            for target in (alice,bob,carol): self.assertEqual(receive(target).type,'bye')
            self.assertLess(time.monotonic()-start,.7)
            wait_until(lambda:server.manager.discarded==2)
            self.assertEqual(sum(r['cancelled'] for r in self.rows('chat_delay_completed')),2)
