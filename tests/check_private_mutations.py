"""Prove both original bug classes are detected, without changing source files."""
import io
import threading
import time
import unittest
from dataclasses import replace
from unittest.mock import patch

from cse3461_chat.dispatch import Publisher
from cse3461_chat.protocol import PrivateRequest, ProtocolError, decode_payload
from cse3461_chat.transport import FramedConnection, ReceiveInfo
from tests.test_private import PrivateWireTests


def main():
    publish=Publisher.publish
    receive=FramedConnection.receive
    def truncate(self,ctx,request,plan):
        if isinstance(request,PrivateRequest):
            request=replace(request,text=request.text[:195])
        return publish(self,ctx,request,plan)
    def one_recv(self,deadline_ns):
        if not threading.current_thread().name.startswith('receiver-'):
            return receive(self,deadline_ns)
        header=self.socket.recv(4)
        if not header:
            return None
        size=int.from_bytes(header,'big')
        body=self.socket.recv(size)  # Deliberately wrong: recv is not a frame boundary.
        self.last_receive=ReceiveInfo(len(body),time.monotonic_ns())
        result=decode_payload(body)
        if isinstance(result,ProtocolError):
            raise result
        return result
    survived=[]
    for name,owner,method,mutation,test in [
        ('truncate body at 195 characters',Publisher,'publish',truncate,'test_300_byte_body_is_complete_and_private'),
        ('dispatch one recv as a complete payload',FramedConnection,'receive',one_recv,'test_fragmented_body_waits_for_complete_frame')]:
        output=io.StringIO()
        with patch.object(owner,method,mutation):
            result=unittest.TextTestRunner(stream=output,verbosity=2).run(unittest.TestSuite([PrivateWireTests(test)]))
        caught=len(result.failures)==1 and not result.errors
        print(name,':', 'DETECTED' if caught else 'NOT CONFIRMED')
        print(output.getvalue())
        if not caught:
            survived.append(name)
    print('Both mutations detected:',not survived)
    return 1 if survived else 0


if __name__=='__main__':
    raise SystemExit(main())
