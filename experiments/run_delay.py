"""Nine real localhost runs. New output directory required; no dependency install."""
import argparse
import hashlib
import json
import platform
import signal
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

from experiments.analyze_delay import analyze_directory, normal_acceptance, main as analyze_main
from tests.support import ProcessClient, free_port
from tests.test_private import wait_until

ROOT=Path(__file__).resolve().parents[1]
CONDITIONS={'baseline':['--features','f2'],
            'fixed':['--features','f2,f3','--delay-mode','fixed','--delay-ms','20'],
            'jitter':['--features','f2,f3','--delay-mode','jitter','--delay-ms','20','--jitter-ms','15']}


def live_receipts(folder):
    count=0
    for name in ['bob','carol']:
        path=folder/(name+'.jsonl')
        if path.exists():
            for line in path.read_text().splitlines(keepends=True):
                if line.endswith('\n') and json.loads(line)['event']=='chat_received': count+=1
    return count


def run_one(root, condition, repeat):
    folder=root/f'{repeat:02d}-{condition}'; folder.mkdir()
    run_id=folder.name; port=free_port(); seed=20261020+repeat
    server_args=[sys.executable,'-u','-m','cse3461_chat.server','--port',str(port),*CONDITIONS[condition],
                 '--delay-seed',str(seed),'--run-id',run_id,'--log-file',str(folder/'server.jsonl')]
    sender_args=[sys.executable,'-u','-m','experiments.sender','--port',str(port),'--run-id',run_id,'--log-file',str(folder/'sender.jsonl')]
    manifest=dict(run_id=run_id,condition=condition,repeat=repeat,seed=seed,
        started_utc=datetime.now(timezone.utc).isoformat(),mode='localhost',real_devices=False,
        planned_messages=60,text_bytes=256,target_interval_ms=2,clients=['sender','bob','carol','observer'],
        recipient_messages=dict(bob=30,carol=30),collection_timeout_s=10,post_complete_grace_s=.2,
        python=sys.version,executable=sys.executable,platform=platform.platform(),
        server_command=server_args,sender_command=sender_args,client_commands={},
        git_head=subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip(),
        git_branch=subprocess.check_output(['git','branch','--show-current'],cwd=ROOT,text=True).strip(),
        git_status=subprocess.check_output(['git','status','--short'],cwd=ROOT,text=True),
        source_sha256={str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest()
            for dirname in ['cse3461_chat','experiments','tests'] for p in sorted((ROOT/dirname).rglob('*.py'))},
        error=None,exit_codes={},collection_complete=False)
    (folder/'manifest.json').write_text(json.dumps(manifest,indent=2)+'\n')
    clients={}; server=sender=None; outputs=[]
    try:
        server_out=(folder/'server-terminal.txt').open('x'); outputs.append(server_out)
        server=subprocess.Popen(server_args,cwd=ROOT,stdout=server_out,stderr=subprocess.STDOUT,text=True)
        wait_until(lambda:'Listening on' in (folder/'server-terminal.txt').read_text(),5)
        for name in ['bob','carol','observer']:
            extra=['--run-id',run_id,'--log-file',str(folder/(name+'.jsonl'))]
            manifest['client_commands'][name]=[sys.executable,'-u','-m','cse3461_chat.client','--port',str(port),'--username',name,*extra]
            clients[name]=ProcessClient(port,name,extra); clients[name].wait_for('[registered]',5)
        sender_out=(folder/'sender-terminal.txt').open('x'); outputs.append(sender_out)
        sender=subprocess.Popen(sender_args,cwd=ROOT,stdin=subprocess.PIPE,stdout=sender_out,stderr=subprocess.STDOUT,text=True)
        wait_until(lambda:'READY\n' in (folder/'sender-terminal.txt').read_text(),5)
        sender.stdin.write('GO\n'); sender.stdin.flush()
        wait_until(lambda:'SENT\n' in (folder/'sender-terminal.txt').read_text(),15)
        start=time.monotonic(); deadline=start+10
        while time.monotonic()<deadline and live_receipts(folder)<60:
            time.sleep(.01)
        manifest['collection_complete']=live_receipts(folder)>=60
        manifest['collection_elapsed_s']=time.monotonic()-start
        if manifest['collection_complete']: time.sleep(.2)
        server.send_signal(signal.SIGTERM)
        manifest['exit_codes']['server']=server.wait(5)
        manifest['exit_codes']['sender']=sender.wait(5)
        for name,client in clients.items(): manifest['exit_codes'][name]=client.finish(5)
    except Exception as exc:
        manifest['error']=repr(exc)
    finally:
        for process in [sender,server]:
            if process and process.poll() is None:
                process.terminate()
                try: process.wait(5)
                except subprocess.TimeoutExpired: process.kill(); process.wait(2)
        if sender and sender.stdin: sender.stdin.close()
        for client in clients.values(): client.close()
        for output in outputs: output.close()
        if server: manifest['exit_codes']['server']=server.returncode
        if sender: manifest['exit_codes']['sender']=sender.returncode
        for name,client in clients.items(): manifest['exit_codes'][name]=client.process.returncode
        (folder/'client-transcripts.json').write_text(json.dumps({n:c.lines for n,c in clients.items()},indent=2)+'\n')
        manifest['log_sha256']={p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in folder.glob('*.jsonl')}
        manifest['finished_utc']=datetime.now(timezone.utc).isoformat()
        (folder/'manifest.json').write_text(json.dumps(manifest,indent=2)+'\n')
    try:
        summary=analyze_directory(folder)
        passed=normal_acceptance(summary) and manifest['collection_complete']
        (folder/'checked-summary.json').write_text(json.dumps(dict(normal_acceptance=passed,metrics=summary),indent=2)+'\n')
    except Exception as exc:
        passed=False
        (folder/'analysis-error.txt').write_text(repr(exc)+'\n')
    print(json.dumps(dict(run=run_id,passed=passed,error=manifest['error'])),flush=True)
    return passed


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__); parser.add_argument('--output',required=True)
    args=parser.parse_args(argv); root=Path(args.output).resolve(); root.mkdir(parents=True,exist_ok=False)
    order=list(CONDITIONS); passed=[]
    for repeat in range(1,4):
        for condition in order[repeat-1:]+order[:repeat-1]:
            passed.append(run_one(root,condition,repeat))
    try: analyze_main(['--input',str(root)])
    except Exception as exc:
        (root/'analysis-error.txt').write_text(repr(exc)+'\n'); return 1
    return 0 if all(passed) else 1


if __name__=='__main__':
    raise SystemExit(main())
