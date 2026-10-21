import contextlib
import json
import socket
import struct
import threading
import time
import subprocess
import sys
import queue
from pathlib import Path

from cse3461_chat.config import ServerConfig
from cse3461_chat.features import build_handlers
from cse3461_chat.server import ServerRuntime
from cse3461_chat.telemetry import EventSink
from cse3461_chat.transport import FramedConnection


def free_port():
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(('127.0.0.1', 0))
        return sock.getsockname()[1]


def raw_send(channel, kind, rid, data, version=1):
    body = json.dumps(dict(v=version, type=kind, request_id=rid, data=data)).encode()
    channel.socket.sendall(struct.pack('!I', len(body))+body)


def receive(channel, seconds=2):
    return channel.receive(time.monotonic_ns()+int(seconds*1e9))


class ProcessClient:
    """Real CLI subprocess with continuously drained output, owned by its test."""
    def __init__(self, port, username='alice', extra=()):
        args=[sys.executable,'-u','-m','cse3461_chat.client','--port',str(port)]
        if username is not None:
            args += ['--username',username]
        self.process=subprocess.Popen(args+list(extra),stdin=subprocess.PIPE,stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,text=True,bufsize=1,cwd=Path(__file__).resolve().parents[1])
        self.lines=[]
        self.queue=queue.Queue()
        def collect():
            for line in self.process.stdout:
                self.lines.append(line)
                self.queue.put(line)
        self.reader=threading.Thread(target=collect,daemon=True)
        self.reader.start()

    def wait_for(self, text, timeout=3):
        deadline=time.monotonic()+timeout
        while time.monotonic()<deadline:
            try:
                line=self.queue.get(timeout=max(.001,deadline-time.monotonic()))
            except queue.Empty:
                break
            if text in line:
                return line
        raise AssertionError(f'Missing {text!r}: '+''.join(self.lines))

    def send(self, line):
        self.process.stdin.write(line+'\n')
        self.process.stdin.flush()

    def finish(self, timeout=5):
        code=self.process.wait(timeout)
        self.reader.join(1)
        return code

    def close(self):
        if self.process.poll() is None:
            self.process.terminate()
            try:
                self.process.wait(5)
            except subprocess.TimeoutExpired:
                self.process.kill()
                self.process.wait(2)
        if self.process.stdin:
            self.process.stdin.close()
        self.reader.join(1)
        self.process.stdout.close()


@contextlib.contextmanager
def running_server(max_clients=16, events=None, handlers=None, server_config=None):
    server = ServerRuntime(output=lambda text: None)
    result = []
    config = server_config or ServerConfig(port=free_port(), max_clients=max_clients)
    worker = threading.Thread(target=lambda: result.append(server.run(config, handlers or build_handlers(config.features), events or EventSink('server'))))
    worker.start()
    if not server.ready.wait(3):
        server.stop('test_setup_failed')
        worker.join(5)
        raise AssertionError('Server did not become ready.')
    channels = []
    def connect(username=None):
        ch = FramedConnection(socket.create_connection(server.address, timeout=2))
        channels.append(ch)
        hello = receive(ch)
        if username is not None:
            raw_send(ch, 'register', 1, {'username': username})
            reply = receive(ch)
            if reply.type != 'registered':
                raise AssertionError(reply)
        return ch, hello
    try:
        yield server, connect
    finally:
        for ch in channels:
            ch.close()
        server.stop('server_shutdown')
        worker.join(5)
        if worker.is_alive():
            raise AssertionError('Server workers did not shut down.')
