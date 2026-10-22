"""Actual F1/F2 CLI and F1+F3 evidence in off, fixed and jitter modes; localhost only."""
import argparse
from collections import Counter
import hashlib
import json
import platform
import signal
import statistics
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

from tests.support import ProcessClient, free_port
from tests.test_private import wait_until

ROOT = Path(__file__).resolve().parents[1]
CONDITIONS = {'baseline':['--features','f1,f2'],
              'fixed':['--features','f1,f2,f3','--delay-mode','fixed','--delay-ms','20'],
              'jitter':['--features','f1,f2,f3','--delay-mode','jitter','--delay-ms','20','--jitter-ms','15']}


def run_one(root, condition):
    folder = root/condition; folder.mkdir()
    port = free_port(); run_id = folder.name
    clients = {}; commands = []; checks = []; codes = {}; error = None
    server = output = None
    server_args = [sys.executable,'-u','-m','cse3461_chat.server','--port',str(port),
        *CONDITIONS[condition],'--delay-seed','20261021','--run-id',run_id,'--log-file',str(folder/'server.jsonl')]
    manifest = dict(mode='localhost', real_devices=False, condition=condition, seed=20261021,
        started_utc=datetime.now(timezone.utc).isoformat(), python=sys.version, executable=sys.executable,
        platform=platform.platform(), server_command=server_args, client_commands={},
        git_head=subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip(),
        git_branch=subprocess.check_output(['git','branch','--show-current'],cwd=ROOT,text=True).strip(),
        git_status=subprocess.check_output(['git','status','--short'],cwd=ROOT,text=True),
        source_sha256={str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest()
            for dirname in ('cse3461_chat','tests','experiments') for p in sorted((ROOT/dirname).rglob('*.py'))})
    metrics = {}
    def check(name, value):
        checks.append(dict(test=name, passed=bool(value)))
        if not value: raise AssertionError(name)
    def send(name, text):
        commands.append(dict(client=name, input=text)); clients[name].send(text)
    def start(key, username):
        extra = ['--run-id',run_id,'--log-file',str(folder/(key+'.jsonl'))]
        clients[key] = ProcessClient(port, username, extra)
        manifest['client_commands'][key] = [sys.executable,'-u','-m','cse3461_chat.client','--port',str(port),'--username',username,*extra]
        clients[key].wait_for('[registered]',5)
        return clients[key]
    try:
        output = (folder/'server-terminal.txt').open('x')
        server = subprocess.Popen(server_args,cwd=ROOT,stdout=output,stderr=subprocess.STDOUT,text=True)
        wait_until(lambda:'Listening on' in (folder/'server-terminal.txt').read_text(),5)
        alice=start('alice','alice'); bob=start('bob','bob'); carol=start('carol','carol')
        for i in range(12):
            text=f'B{i:02d} '+'你好🙂'*25+'xy' # 256 UTF-8 bytes
            check(f'body {i} is 256 bytes',len(text.encode())==256)
            send('alice',('/all ' if i%2 else '')+text)
            alice.wait_for('[queue result]',5)
        for i in range(12):
            text=f'B{i:02d} '+'你好🙂'*25+'xy'
            for client in (bob,carol): client.wait_for('[broadcast] alice: '+text,5)
        check('all 12 full Unicode broadcasts displayed on both recipients',True)
        send('bob','/all reverse 中文')
        bob.wait_for('[queue result]',5)
        for client in (alice,carol): client.wait_for('[broadcast] bob: reverse 中文',5)
        send('alice','@bob PRIVATE_ONLY_123')
        alice.wait_for('[queue result]',5); bob.wait_for('[private] alice: PRIVATE_ONLY_123',5)
        for text, expected in [('@missing secret','USER_NOT_FOUND'),('@alice secret','SELF_TARGET'),('@broken','[usage]')]:
            send('alice',text); alice.wait_for(expected,5)
        send('bob','/quit'); codes['bob']=bob.finish(5)
        new=start('bob-reconnected','bob')
        send('alice','/all after reconnect')
        alice.wait_for('[queue result]',5)
        for client in (new,carol): client.wait_for('[broadcast] alice: after reconnect',5)
        # Actual no-recipient result after both peers leave; later registration remains usable.
        for name in ('bob-reconnected','carol'):
            send(name,'/quit'); codes[name]=clients[name].finish(5)
        send('alice','alone'); alice.wait_for('NO_RECIPIENTS',5)
        check('no recipients is nonfatal',alice.process.poll() is None)
        server.send_signal(signal.SIGTERM); codes['server']=server.wait(5)
        codes['alice']=alice.finish(5)
        check('all processes exit zero',all(v==0 for v in codes.values()))
        logs={name:[json.loads(line) for line in (folder/(name+'.jsonl')).read_text().splitlines()]
              for name in ('server',*clients)}
        for name,rows in logs.items():
            check(name+' log sequence complete',[r['seq'] for r in rows]==list(range(1,len(rows)+1)))
            check(name+' final telemetry valid',rows[-1]['event']=='process_stopped' and rows[-1]['fields']['telemetry_valid'])
        routes=[r['fields'] for r in logs['server'] if r['event']=='route_selected']
        broadcasts=[r for r in routes if r['feature']=='f1']; private=[r for r in routes if r['feature']=='f2']
        expected=Counter((r['message_id'],target) for r in routes for target in r['target_session_ids'])
        received=Counter((r['fields']['message_id'],r['fields']['receiver_session_id'])
                         for name in clients for r in logs[name] if r['event']=='chat_received')
        check('exact selected target pairs received once, no unexpected or echo',received==expected and all(n==1 for n in received.values()))
        check('14 broadcasts and one isolated private route',len(broadcasts)==14 and len(private)==1 and len(expected)==29)
        check('broadcast recipient count two; private one',all(r['selected_count']==2 for r in broadcasts) and private[0]['selected_count']==1)
        check('origin not a broadcast recipient',all(r['origin_session_id'] not in r['target_session_ids'] for r in broadcasts))
        for name in clients:
            receipts=[r['fields'] for r in logs[name] if r['event']=='chat_received']
            session_ids={r['receiver_session_id'] for r in receipts}
            check(name+' one receiving session',len(session_ids)==1)
            session_id=next(iter(session_ids))
            receipt_ids=[r['message_id'] for r in receipts]
            for origin in {r['origin_session_id'] for r in routes}:
                mids=[r['message_id'] for r in routes if r['origin_session_id']==origin
                      and session_id in r['target_session_ids']]
                check(name+' per-sender FIFO '+origin,[mid for mid in receipt_ids if mid in mids]==mids)
        check('replacement sees only new broadcast',sum(r['event']=='chat_received' for r in logs['bob-reconnected'])==1)
        check('Carol has no private display',not any('[private]' in line for line in carol.lines))
        check('sender has no own broadcast display',not any('[broadcast] alice:' in line for line in alice.lines))
        admitted=Counter((r['fields']['message_id'],r['fields']['target_session_id']) for r in logs['server']
                         if r['event']=='outbound_enqueued' and r['fields'].get('message_id'))
        written=Counter((r['fields']['message_id'],r['fields']['target_session_id']) for r in logs['server']
                        if r['event']=='frame_write_completed' and r['fields'].get('message_id'))
        check('admission and completed writes match observed target pairs',admitted==expected and written==expected)
        waits=[r['fields'] for r in logs['server'] if r['event']=='chat_delay_completed' and r['fields']['feature']=='f1']
        check('28 broadcast wait observations; no cancellation',len(waits)==28 and all(not r['cancelled'] for r in waits))
        lo,hi=(0,0) if condition=='baseline' else (20,20) if condition=='fixed' else (5,35)
        check('selected delays in configured interval',all(lo<=r['selected_ms']<=hi for r in waits))
        check('actual waits computed from local timestamps',all(r['actual_wait_ns']==r['wait_ended_ns']-r['wait_started_ns'] for r in waits))
        metrics=dict(selected_pairs=len(expected),received_pairs=sum(received.values()),broadcast_pairs=28,private_pairs=1,
            broadcast_wait_samples=len(waits), selected_min_ms=min(r['selected_ms'] for r in waits),
            selected_max_ms=max(r['selected_ms'] for r in waits),
            actual_wait_mean_ms=statistics.mean(r['actual_wait_ns']/1e6 for r in waits),
            queue_mean_ms=statistics.mean(r['queue_only_ns']/1e6 for r in waits))
    except Exception as exc:
        error=repr(exc)
    finally:
        if server and server.poll() is None:
            server.terminate()
            try: server.wait(5)
            except subprocess.TimeoutExpired: server.kill(); server.wait(2)
        for name,client in clients.items():
            client.close(); codes[name]=client.process.returncode
        if server: codes['server']=server.returncode
        if output: output.close()
        manifest.update(finished_utc=datetime.now(timezone.utc).isoformat(), exit_codes=codes, error=error,
            log_sha256={p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in folder.glob('*.jsonl')})
        (folder/'manifest.json').write_text(json.dumps(manifest,indent=2)+'\n')
        (folder/'terminal-transcript.json').write_text(json.dumps(dict(commands=commands,
            output={n:c.lines for n,c in clients.items()}),ensure_ascii=False,indent=2)+'\n')
        summary=dict(passed=error is None and all(c['passed'] for c in checks),checks=checks,
                     metrics=metrics,error=error,exit_codes=codes,real_devices=False)
        (folder/'checked-summary.json').write_text(json.dumps(summary,indent=2)+'\n')
    print(json.dumps(dict(condition=condition,passed=summary['passed'],checks=len(checks),metrics=metrics,error=error)),flush=True)
    return summary['passed']


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__); parser.add_argument('--output',required=True)
    args=parser.parse_args(argv); root=Path(args.output).resolve(); root.mkdir(parents=True,exist_ok=False)
    results=[run_one(root,condition) for condition in CONDITIONS]
    return 0 if all(results) else 1


if __name__=='__main__': raise SystemExit(main())
