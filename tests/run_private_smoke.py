"""Reproducible localhost F2 evidence using the actual server and client CLIs.

Run: python3 -m tests.run_private_smoke --output outputs/runs/<new-directory>
This is a scripted demonstration, not a real-device or student video demonstration.
"""
import argparse
import hashlib
import json
import platform
import signal
import subprocess
import sys
import time
from pathlib import Path

from tests.support import ProcessClient, free_port
from tests.test_private import wait_until


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',required=True)
    args=parser.parse_args()
    folder=Path(args.output).resolve()
    folder.mkdir(parents=True,exist_ok=False)
    root=Path(__file__).resolve().parents[1]
    port=free_port()
    run_id=folder.name
    clients={}
    commands=[]
    checks=[]
    server=None
    stdout=None
    error=None
    codes={}
    def check(name,condition):
        checks.append(dict(test=name,passed=bool(condition)))
        if not condition:
            raise AssertionError(name)
    def send(name,line):
        commands.append(dict(client=name,input=line))
        clients[name].send(line)
    def start(name,username):
        client=ProcessClient(port,username,('--run-id',run_id,'--log-file',str(folder/(name+'.jsonl'))))
        clients[name]=client
        client.wait_for('[registered]')
        return client
    server_args=[sys.executable,'-u','-m','cse3461_chat.server','--host','127.0.0.1',
        '--port',str(port),'--features','f2','--run-id',run_id,'--log-file',str(folder/'server.jsonl')]
    environment=dict(python=sys.version,executable=sys.executable,platform=platform.platform(),
        mode='localhost',server_command=server_args,client_command_template=[sys.executable,'-u','-m',
        'cse3461_chat.client','--port',str(port),'--username','<username>','--run-id',run_id,'--log-file','<new-file>'],
        source_sha256={str(p.relative_to(root)):hashlib.sha256(p.read_bytes()).hexdigest()
                       for p in sorted((root/'cse3461_chat').rglob('*.py'))})
    (folder/'environment.json').write_text(json.dumps(environment,indent=2)+'\n')
    try:
        stdout=(folder/'server-terminal.txt').open('x')
        server=subprocess.Popen(server_args,cwd=root,stdout=stdout,stderr=subprocess.STDOUT,text=True)
        wait_until(lambda: 'Listening on' in (folder/'server-terminal.txt').read_text(),3)
        alice=start('alice','alice')
        bob=start('bob','bob')
        carol=start('carol','carol')
        send('alice','@bob '+'x'*300)
        alice.wait_for('[queue result]')
        bob.wait_for('[private] alice: '+'x'*300)
        check('300-byte complete body in actual CLI',True)
        send('bob','@alice 中文回复')
        bob.wait_for('[queue result]')
        alice.wait_for('[private] bob: 中文回复')
        check('reverse Unicode private message in actual CLI',True)
        for command,expected in [('@missing hello','USER_NOT_FOUND'),('@alice hello','SELF_TARGET'),
                                  ('@broken','[usage]'),('broadcast stays disabled under f2','FEATURE_DISABLED'),
                                  ('/enhance','FEATURE_NOT_IMPLEMENTED')]:
            send('alice',command)
            alice.wait_for(expected)
            check(command.split()[0]+' -> '+expected,True)
        send('alice','/help')
        alice.wait_for('F2=enabled')
        send('bob','/quit')
        codes['bob']=bob.finish()
        check('original Bob exits cleanly',codes['bob']==0)
        send('alice','@bob disconnected')
        alice.wait_for('USER_NOT_FOUND')
        check('disconnected target is absent',True)
        new=start('bob-reconnected','bob')
        send('alice','@bob new session')
        alice.wait_for('[queue result]')
        new.wait_for('[private] alice: new session')
        check('same-name reconnect receives new traffic',True)
        # Termination drains accepted traffic and gives a bounded end for transcript checks.
        server.send_signal(signal.SIGTERM)
        codes['server']=server.wait(5)
        for name,client in clients.items():
            codes[name]=client.finish()
        check('all processes exit zero',all(code==0 for code in codes.values()))
        check('Carol receives no private event',not any('[private]' in line for line in carol.lines))
        check('Alice receives no own private echo',not any('[private] alice:' in line for line in alice.lines))
        check('replacement Bob receives no previous session body',not any('x'*300 in line for line in new.lines))
        logs={name:[json.loads(line) for line in (folder/(name+'.jsonl')).read_text().splitlines()]
              for name in ['server',*clients]}
        for name,rows in logs.items():
            check(name+' telemetry sequence valid',[r['seq'] for r in rows]==list(range(1,len(rows)+1)))
            check(name+' final telemetry valid',rows[-1]['event']=='process_stopped' and rows[-1]['fields']['telemetry_valid'])
            check(name+' logs omit private bodies',not any('x'*300 in json.dumps(r) or '中文回复' in json.dumps(r,ensure_ascii=False) for r in rows))
        starts=[r for r in logs['server'] if r['event']=='process_started']
        check('server logged enabled F2',starts[0]['fields']['capabilities']['f2']==dict(implemented=True,enabled=True,variant=None))
        routes=[r['fields'] for r in logs['server'] if r['event']=='route_selected']
        names={r['fields']['session_id']:r['fields']['requested_username'] for r in logs['server']
               if r['event']=='registration_result' and r['fields']['accepted']}
        check('exactly three successful one-target routes',len(routes)==3 and all(r['selected_count']==1 for r in routes))
        check('no bystander route or origin echo',all(names[r['target_session_ids'][0]]!='carol' and r['origin_session_id'] not in r['target_session_ids'] for r in routes))
    except BaseException as exc:
        error=repr(exc)
    finally:
        if server is not None and server.poll() is None:
            server.terminate()
            try:
                server.wait(5)
            except subprocess.TimeoutExpired:
                server.kill()
                server.wait(2)
        for client in clients.values():
            client.close()
        if stdout:
            stdout.close()
        (folder/'terminal-transcript.json').write_text(json.dumps(dict(commands=commands,
            output={name:client.lines for name,client in clients.items()}),ensure_ascii=False,indent=2)+'\n')
        summary=dict(passed=error is None and all(c['passed'] for c in checks),checks=checks,
            exit_codes=codes,error=error,mode='localhost',real_device_verified=False)
        (folder/'smoke-summary.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps(dict(output=str(folder),passed=summary['passed'],checks=len(checks),error=error)))
    return 0 if summary['passed'] else 1


if __name__=='__main__':
    sys.exit(main())
