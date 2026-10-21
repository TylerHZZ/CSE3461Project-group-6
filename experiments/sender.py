"""Finite workload driver using the unchanged production ClientRuntime wire path."""
import argparse
import sys
import time
from cse3461_chat.client import ClientRuntime
from cse3461_chat.config import ClientConfig
from cse3461_chat.protocol import Disconnected
from cse3461_chat.telemetry import open_event_sink


def await_event(client, kind, request_id=None, timeout=5):
    deadline = time.monotonic()+timeout
    while time.monotonic()<deadline:
        event = client.next_event(.001)
        if isinstance(event, Disconnected) or client.state == 'CLOSED':
            raise RuntimeError('Disconnected before expected response.')
        if event and (event.type==kind or event.type=='error') and (request_id is None or event.request_id==request_id):
            return event
    raise TimeoutError('Response deadline; outcome unknown, no retry.')


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--port',type=int,required=True)
    parser.add_argument('--run-id',required=True)
    parser.add_argument('--log-file',required=True)
    args=parser.parse_args(argv)
    client=ClientRuntime(); events=open_event_sink('client',args.run_id,args.log_file)
    code=0
    try:
        client.connect(ClientConfig(port=args.port,username='sender',run_id=args.run_id,log_file=args.log_file),events)
        await_event(client,'hello')
        rid=client.send('register',dict(username='sender'))
        if await_event(client,'registered',rid).type!='registered': raise RuntimeError('Registration failed.')
        print('READY',flush=True)
        if sys.stdin.readline().strip()!='GO': raise RuntimeError('Missing controller start.')
        next_send=time.monotonic()
        for index in range(60):
            time.sleep(max(0,next_send-time.monotonic()))
            target=('bob','carol')[index%2]
            text=f'{index:04d}:'+'x'*251
            events.emit('workload_attempt',dict(index=index,target=target,text_bytes=256))
            rid=client.send('private_send',dict(to=target,text=text))
            result=await_event(client,'send_result',rid,10)
            events.emit('workload_result',dict(index=index,request_id=rid,type=result.type,
                status=result.data.get('status'),message_id=result.data.get('message_id'),error_code=result.data.get('code')))
            # Minimum inter-attempt spacing; late sends are not caught up in a burst.
            next_send=max(next_send+.002,time.monotonic())
        events.emit('workload_finished',dict(planned=60))
        print('SENT',flush=True)
        deadline=time.monotonic()+15
        while client.state!='CLOSED' and time.monotonic()<deadline:
            client.next_event(.01)
        if client.state!='CLOSED': raise TimeoutError('Controller did not stop server.')
        if client.close_reason!='server_shutdown': raise RuntimeError('Unexpected sender close: '+str(client.close_reason))
    except Exception as exc:
        code=1; print(repr(exc),file=sys.stderr,flush=True)
    finally:
        client.close('workload_failure' if code else 'server_shutdown')
        if not events.valid: code=1
    return code


if __name__=='__main__':
    raise SystemExit(main())
