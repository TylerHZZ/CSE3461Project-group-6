import socket
import struct
import threading
import time
import unittest
from unittest.mock import patch

from cse3461_chat.protocol import make_message, ProtocolError
from cse3461_chat.transport import FramedConnection, ReadDeadline, encode_frame


class TransportTests(unittest.TestCase):
    def pair(self):
        left, right = socket.socketpair()
        channel = FramedConnection(left)
        self.addCleanup(channel.close)
        self.addCleanup(right.close)
        return channel, right

    def test_fragmented_multibyte_frame(self):
        msg = make_message('broadcast_send', 1, {'text': 'é好'})
        frame = encode_frame(msg)
        self.assertEqual(struct.unpack('!I', frame[:4])[0], len(frame)-4)
        for split in [1, 2, 3, frame.index('é'.encode())+1]:
            channel, peer = self.pair()
            def send():
                peer.sendall(frame[:split])
                time.sleep(.01)
                peer.sendall(frame[split:])
            worker = threading.Thread(target=send)
            worker.start()
            self.assertEqual(channel.receive(None).data, {'text': 'é好'})
            worker.join(1)
            self.assertEqual(channel.last_receive.payload_bytes, len(frame)-4)

    def test_coalesced_frames(self):
        channel, peer = self.pair()
        peer.sendall(encode_frame(make_message('register', 1, {'username': 'bob'})) +
                     encode_frame(make_message('disconnect', 2, {})))
        self.assertEqual([channel.receive(None).type, channel.receive(None).type], ['register', 'disconnect'])

    def test_idle_and_partial_deadlines(self):
        channel, peer = self.pair()
        worker = threading.Thread(target=lambda: (time.sleep(1.05), peer.sendall(encode_frame(make_message('disconnect', 1, {})))))
        worker.start()
        self.assertEqual(channel.receive(None).type, 'disconnect')
        worker.join(1)
        with self.assertRaises(ReadDeadline):
            channel.receive(time.monotonic_ns()+20_000_000)
        peer.sendall(b'\x00')
        with patch('cse3461_chat.transport.PARTIAL_FRAME_S', .04):
            with self.assertRaises(ProtocolError) as err:
                channel.receive(None)
        self.assertEqual(err.exception.code, 'FRAME_TIMEOUT')

    def test_eof_boundaries(self):
        for data, code in [(b'', None), (b'\x00\x00', 'TRUNCATED_FRAME'),
                           (struct.pack('!I', 10)+b'{', 'TRUNCATED_FRAME')]:
            channel, peer = self.pair()
            peer.sendall(data)
            peer.shutdown(socket.SHUT_WR)
            if code:
                with self.assertRaises(ProtocolError) as err:
                    channel.receive(None)
                self.assertEqual(err.exception.code, code)
            else:
                self.assertIsNone(channel.receive(None))

    def test_length_and_failed_write(self):
        for size, code in [(0, 'BAD_FRAME'), (65537, 'FRAME_TOO_LARGE')]:
            channel, peer = self.pair()
            peer.sendall(struct.pack('!I', size))
            with self.assertRaises(ProtocolError) as err:
                channel.receive(None)
            self.assertEqual(err.exception.code, code)
        channel, peer = self.pair()
        peer.close()
        with self.assertRaises(OSError):
            channel.write(make_message('disconnect', 1, {}))
        with self.assertRaises(OSError):
            channel.write(make_message('disconnect', 2, {}))
        channel.close()
        channel.close()

    def test_close_unblocks_read(self):
        channel, peer = self.pair()
        stopped = threading.Event()
        def read():
            try:
                channel.receive(None)
            except OSError:
                pass
            finally:
                stopped.set()
        worker = threading.Thread(target=read)
        worker.start()
        channel.close()
        self.assertTrue(stopped.wait(1.2))
        worker.join(1)
