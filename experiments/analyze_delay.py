"""Strict local-log analysis. No cross-process timestamp subtraction."""
import argparse
import csv
import hashlib
import json
import math
from pathlib import Path
import statistics


def distribution(prefix, values):
    values = sorted(values)
    return {prefix+'_n':len(values), **{prefix+'_'+key: value for key,value in (
        ('mean_ms', statistics.fmean(values) if values else None),
        ('p50_ms', values[math.ceil(.5*len(values))-1] if values else None),
        ('p95_ms', values[math.ceil(.95*len(values))-1] if values else None),
        ('min_ms', values[0] if values else None), ('max_ms', values[-1] if values else None))}}


def summarize(manifest, logs):
    names = ['server', *manifest['clients']]
    if set(logs) != set(names) or set(manifest['exit_codes']) != set(names):
        raise ValueError('Missing process log or exit status; evidence incomplete.')
    if manifest.get('error') or any(manifest['exit_codes'].values()):
        raise ValueError('Run did not complete cleanly; retain raw evidence, do not report success.')
    for name, rows in logs.items():
        if (not rows or [r['seq'] for r in rows] != list(range(1,len(rows)+1)) or
            {r['run_id'] for r in rows} != {manifest['run_id']} or len({r['process_id'] for r in rows}) != 1 or
            rows[0]['event'] != 'process_started' or rows[-1]['event'] != 'process_stopped' or
            not rows[-1]['fields'].get('clean') or not rows[-1]['fields'].get('telemetry_valid')):
            raise ValueError(f'{name}: invalid sequence, run identity or lifecycle evidence.')
    def fields(name, event):
        return [r['fields'] for r in logs[name] if r['event']==event]
    def key(f): return f['message_id'], f['target_session_id']
    sessions = {f['requested_username']:f['session_id'] for f in fields('server','registration_result') if f['accepted']}
    if not set(manifest['clients']) <= sessions.keys():
        raise ValueError('Missing registered participant.')
    sent = fields('sender','client_request_sent')
    sent = [f for f in sent if f['type']=='private_send']
    sent_ids = {f['request_id'] for f in sent}
    if len(sent_ids)!=len(sent): raise ValueError('Duplicate sender request ID.')
    routes = fields('server','route_selected')
    origin_ids = [f['origin_request_id'] for f in routes]
    if len(set(origin_ids)) != len(origin_ids) or any(f['selected_count'] != 1 or len(f['target_session_ids']) != 1 for f in routes):
        raise ValueError('One private request must produce exactly one unique route.')
    settings = {'baseline':('f2','off',0,0), 'fixed':('f2,f3','fixed',20,0),
                'jitter':('f2,f3','jitter',20,15)}
    if manifest.get('condition') not in settings: raise ValueError('Unknown experiment condition.')
    features, mode, delay, jitter = settings[manifest['condition']]
    starts = fields('server','process_started')
    cfg = starts[0]['config']
    if len(starts)!=1 or any(cfg.get(k)!=v for k,v in dict(features=features,delay_mode=mode,
            delay_ms=delay,jitter_ms=jitter,delay_seed=manifest['seed']).items()):
        raise ValueError('Actual server configuration does not match treatment manifest.')
    selected = {(f['message_id'], sid) for f in routes for sid in f['target_session_ids']}
    if sum(f['selected_count'] for f in routes) != len(selected):
        raise ValueError('Inconsistent route denominator.')
    if any(f['origin_session_id'] != sessions['sender'] or f['origin_request_id'] not in sent_ids for f in routes):
        raise ValueError('Route not correlated to logged sender.')
    attempts = fields('sender','workload_attempt')
    results = fields('sender','workload_result')
    attempt_by_index = {f['index']:f for f in attempts}
    result_by_request = {f['request_id']:f for f in results}
    if (list(attempt_by_index)!=list(range(manifest['planned_messages'])) or
        len(attempts)!=len(attempt_by_index) or len(results)!=len(result_by_request) or
        set(result_by_request)!=sent_ids or len({f['index'] for f in results})!=len(results) or
        any(f['text_bytes']!=manifest['text_bytes'] or f['target'] not in ('bob','carol') for f in attempts)):
        raise ValueError('Missing or duplicated workload attempt/result correspondence.')
    route_by_request = {f['origin_request_id']:f for f in routes}
    for rid,result in result_by_request.items():
        attempt = attempt_by_index.get(result['index'])
        if attempt is None: raise ValueError('Result lacks workload attempt.')
        route = route_by_request.get(rid)
        if route is None:
            if result['type']!='error': raise ValueError('Unrouted request lacks rejection result.')
        elif (result['type']!='send_result' or result['message_id']!=route['message_id'] or
              route['target_session_ids'] != [sessions[attempt['target']]]):
            raise ValueError('Queue result or selected recipient mismatches workload request.')
    route_by_pair = {(f['message_id'],sid):f for f in routes for sid in f['target_session_ids']}
    receipts = []
    per_recipient = {}
    for name in manifest['clients']:
        rows = fields(name, 'chat_received')
        if any(f['receiver_session_id'] != sessions[name] or f['text_bytes'] != manifest['text_bytes'] or f['sender']!='sender' or f['mode']!='private' for f in rows):
            raise ValueError('Incorrect recipient identity or payload length.')
        receipts += [(f['message_id'],f['receiver_session_id']) for f in rows]
        unique = {f['message_id']:f for f in rows}
        times = sorted(f['received_ns'] for f in unique.values())
        per_recipient[name+'_received'] = len(unique)
        per_recipient[name+'_mps'] = ((len(times)-1)*1e9/(times[-1]-times[0])
            if len(times)>=2 and times[-1]>times[0] else None)
    seen = set(receipts)
    admitted = {key(f) for f in fields('server','outbound_enqueued') if f['frame_type']=='chat_message'}
    not_queued = {key(f) for f in fields('server','outbound_not_queued') if f['frame_type']=='chat_message'}
    writes = [f for f in fields('server','frame_write_completed') if f['frame_type']=='chat_message']
    waits = fields('server','chat_delay_completed')
    cancelled = [f for f in waits if f['cancelled']]
    completed_waits = [f for f in waits if not f['cancelled']]
    if not admitted <= selected or not not_queued <= selected or admitted & not_queued:
        raise ValueError('Admission does not match selected pairs.')
    def index(event):
        rows = [f for f in fields('server',event) if f.get('frame_type','chat_message')=='chat_message']
        result = {key(f):f for f in rows}
        if len(result)!=len(rows): raise ValueError('Duplicate server event: '+event)
        return result
    enqueued, rejected = index('outbound_enqueued'), index('outbound_not_queued')
    dequeued, waited = index('chat_dequeued'), index('chat_delay_completed')
    completed, failed, discarded = index('frame_write_completed'), index('frame_write_failed'), index('outbound_discarded')
    if set(enqueued)|set(rejected) != selected or set(enqueued)&set(rejected):
        raise ValueError('Missing or conflicting admission outcome.')
    for records in (enqueued,rejected,dequeued,waited,completed,failed,discarded):
        for pair,f in records.items():
            route=route_by_pair.get(pair)
            if (route is None or f.get('feature')!='f2' or f.get('origin_session_id')!=route['origin_session_id'] or
                    f.get('origin_request_id')!=route['origin_request_id']):
                raise ValueError('Delivery metadata does not match routed sender/request/feature.')
    for pair,route in route_by_pair.items():
        expected_status = 'queued' if pair in enqueued else 'not_queued'
        if result_by_request[route['origin_request_id']]['status']!=expected_status:
            raise ValueError('Sender queue result disagrees with actual admission.')
    terminal_keys = list(completed)+list(failed)+list(discarded)
    if set(terminal_keys)!=set(enqueued) or len(terminal_keys)!=len(set(terminal_keys)):
        raise ValueError('Admitted frames lack exactly one terminal write/discard outcome.')
    if set(dequeued)!=set(waited) or not set(waited)<=set(enqueued) or not (set(completed)|set(failed))<=set(waited):
        raise ValueError('Missing dequeue/wait evidence before socket write.')
    for pair,f in waited.items():
        if (f['mode']!=mode or not delay-jitter<=f['selected_ms']<=delay+jitter or
            f['enqueued_ns']!=enqueued[pair]['enqueued_ns'] or
            f['dequeued_ns']!=dequeued[pair]['dequeued_ns'] or
            not f['enqueued_ns']<=f['dequeued_ns']<=f['wait_started_ns']<=f['wait_ended_ns'] or
            f['actual_wait_ns']!=f['wait_ended_ns']-f['wait_started_ns'] or
            f['queue_only_ns']!=f['dequeued_ns']-f['enqueued_ns'] or
            (f['cancelled'] and pair not in discarded) or
            (not f['cancelled'] and f['actual_wait_ns']+1000 < f['selected_ms']*1e6)):
            raise ValueError('Invalid treatment, cancellation or measured wait arithmetic.')
    for pair,f in {**completed, **failed}.items():
        if (f['enqueued_ns']!=enqueued[pair]['enqueued_ns'] or waited[pair]['cancelled'] or
            not waited[pair]['wait_ended_ns']<=f['started_ns']<=f['ended_ns']):
            raise ValueError('Invalid server-local prewrite/write timing.')
    if not (seen & selected)<=set(completed):
        raise ValueError('Observed selected receipt lacks corresponding completed server write.')
    route_order = {(f['message_id'],sid):f['origin_request_id'] for f in routes for sid in f['target_session_ids']}
    fifo_ok = True
    for name in manifest['clients']:
        ids = [route_order.get((f['message_id'],f['receiver_session_id'])) for f in fields(name,'chat_received')]
        known = [rid for rid in ids if rid is not None]
        fifo_ok = fifo_ok and known == sorted(known)
    prewrite = [(f['started_ns']-f['enqueued_ns'])/1e6 for f in writes]
    actual = [f['actual_wait_ns']/1e6 for f in completed_waits]
    queue = [f['queue_only_ns']/1e6 for f in waits]
    if any(v<0 for v in actual+queue+prewrite): raise ValueError('Negative local duration.')
    sent_times = sorted(f['occurred_ns'] for f in sent)
    received = len(seen & selected)
    result = dict(run_id=manifest['run_id'], condition=manifest.get('condition'), repeat=manifest.get('repeat'),
        seed=manifest.get('seed'), planned_messages=manifest['planned_messages'], sent_requests=len(sent),
        unsent_planned=manifest['planned_messages']-len(sent),
        unrouted_requests=len(sent_ids-{f['origin_request_id'] for f in routes}),
        selected_pairs=len(selected), admitted_pairs=len(admitted), not_queued_pairs=len(not_queued),
        admission_unaccounted_pairs=len(selected-admitted-not_queued),
        write_completed_pairs=len({key(f) for f in writes}),
        write_failed_count=len([f for f in fields('server','frame_write_failed') if f['frame_type']=='chat_message']),
        discarded_count=len([f for f in fields('server','outbound_discarded') if f['frame_type']=='chat_message']),
        received_pairs=received, missing_pairs=len(selected-seen),
        observed_delivery_fraction=received/len(selected) if selected else None,
        received_per_sent=received/len(sent) if sent else None,
        fifo_ok=fifo_ok, duplicate_receipts=len(receipts)-len(seen), unexpected_receipts=len(seen-selected),
        prewrite_excluded_pairs=len(selected)-len(writes),
        selected_delay_mean_ms=statistics.fmean(f['selected_ms'] for f in completed_waits) if completed_waits else None,
        sender_span_ms=(sent_times[-1]-sent_times[0])/1e6 if len(sent_times)>1 else None,
        **per_recipient, **distribution('wait_actual',actual), **distribution('queue_only',queue),
        **distribution('prewrite',prewrite), **distribution('cancelled_wait',[f['actual_wait_ns']/1e6 for f in cancelled]))
    return result


def normal_acceptance(summary):
    expected = summary['planned_messages']
    return (all(summary[k]==expected for k in ('sent_requests','selected_pairs','admitted_pairs',
            'write_completed_pairs','received_pairs','wait_actual_n','queue_only_n','prewrite_n')) and
        all(summary[k]==0 for k in ('unsent_planned','unrouted_requests','not_queued_pairs','admission_unaccounted_pairs',
            'write_failed_count','discarded_count','missing_pairs','duplicate_receipts','unexpected_receipts',
            'sender_received','observer_received','cancelled_wait_n','prewrite_excluded_pairs')) and
        summary['bob_received']==summary['carol_received']==expected//2 and summary['fifo_ok'])


def analyze_directory(folder):
    manifest = json.loads((folder/'manifest.json').read_text())
    logs = {}
    for name in ['server',*manifest['clients']]:
        path = folder/(name+'.jsonl')
        raw = path.read_bytes()
        if hashlib.sha256(raw).hexdigest() != manifest['log_sha256'].get(path.name):
            raise ValueError(f'{path}: log hash mismatch.')
        logs[name] = [json.loads(line) for line in raw.splitlines()]
    return summarize(manifest, logs)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--input', required=True, help='Parent containing condition/repetition run directories.')
    args = parser.parse_args(argv)
    root = Path(args.input)
    folders = sorted(p.parent for p in root.glob('*/manifest.json'))
    if not folders: raise ValueError('No run manifests found.')
    results = [analyze_directory(folder) for folder in folders]
    with (root/'summary.csv').open('w',newline='') as stream:
        writer=csv.DictWriter(stream,fieldnames=list(results[0])); writer.writeheader(); writer.writerows(results)
    (root/'summary.json').write_text(json.dumps(results,indent=2,allow_nan=False)+'\n')
    print(json.dumps(dict(runs=len(results), summary=str(root/'summary.csv'))))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
