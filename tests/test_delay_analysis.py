"""Hand-calculated evidence fixtures; missing/lost traffic must not become 100%."""
import copy
import importlib.util
import unittest


def fixture():
    manifest = dict(run_id='fixture', condition='fixed', seed=7, planned_messages=2, text_bytes=256,
                    clients=['sender','bob','carol','observer'], exit_codes={n:0 for n in ['server','sender','bob','carol','observer']}, error=None)
    events = {n:[] for n in manifest['exit_codes']}
    def add(name, event, **fields): events[name].append((event, fields))
    for n in events: add(n, 'process_started', config=dict(features='f2,f3', delay_mode='fixed', delay_ms=20, jitter_ms=0, delay_seed=7))
    for n in manifest['clients']:
        add('server', 'registration_result', session_id=n+'-sid', requested_username=n, accepted=True)
    for rid in [2,3]:
        add('sender', 'workload_attempt', index=rid-2, target='bob', text_bytes=256)
        add('sender', 'workload_result', index=rid-2, request_id=rid, type='send_result', message_id=str(rid), status='queued' if rid==2 else 'not_queued')
        add('sender', 'client_request_sent', type='private_send', request_id=rid, occurred_ns=rid*1_000_000)
        add('server', 'route_selected', message_id=str(rid), origin_session_id='sender-sid', origin_request_id=rid,
            target_session_ids=['bob-sid'], selected_count=1)
    add('server', 'outbound_enqueued', frame_type='chat_message', message_id='2', target_session_id='bob-sid', enqueued_ns=10_000_000)
    add('server', 'outbound_not_queued', frame_type='chat_message', message_id='3', target_session_id='bob-sid', reason='full')
    add('server', 'chat_dequeued', message_id='2', target_session_id='bob-sid', enqueued_ns=10_000_000, dequeued_ns=15_000_000)
    add('server', 'chat_delay_completed', mode='fixed', enqueued_ns=10_000_000, dequeued_ns=15_000_000, wait_started_ns=15_000_000, wait_ended_ns=37_000_000, message_id='2', target_session_id='bob-sid', selected_ms=20,
        actual_wait_ns=22_000_000, queue_only_ns=5_000_000, cancelled=False)
    add('server', 'frame_write_completed', frame_type='chat_message', message_id='2', target_session_id='bob-sid',
        enqueued_ns=10_000_000, started_ns=38_000_000, ended_ns=39_000_000)
    add('bob', 'chat_received', message_id='2', receiver_session_id='bob-sid', sender='sender', mode='private', text_bytes=256, received_ns=900_000_000)
    for event, fields in events['server']:
        if 'target_session_id' in fields:
            fields.update(origin_session_id='sender-sid', origin_request_id=int(fields['message_id']), feature='f2', frame_type='chat_message')
    for n in events: add(n, 'process_stopped', clean=True, telemetry_valid=True)
    logs = {n:[dict(seq=i+1, event=e, fields=f, run_id='fixture', process_id=n) for i,(e,f) in enumerate(rows)] for n,rows in events.items()}
    return manifest, logs


class DelayAnalysisTests(unittest.TestCase):
    def analyze(self, manifest, logs):
        self.assertIsNotNone(importlib.util.find_spec('experiments.analyze_delay'), 'Analyzer missing')
        from experiments.analyze_delay import summarize
        return summarize(manifest, logs)

    def test_full_queue_loss_remains_in_denominator_and_actual_wait_is_measured(self):
        result = self.analyze(*fixture())
        self.assertEqual(result['selected_pairs'], 2)
        self.assertEqual(result['received_pairs'], 1)
        self.assertEqual(result['observed_delivery_fraction'], .5)
        self.assertEqual(result['wait_actual_mean_ms'], 22)
        self.assertEqual(result['queue_only_mean_ms'], 5)
        self.assertEqual(result['prewrite_mean_ms'], 28)
        self.assertEqual(result['prewrite_n'], 1)
        self.assertEqual(result['not_queued_pairs'], 1)
        self.assertIsNone(result['bob_mps'])

    def test_missing_log_invalidates_evidence(self):
        manifest, logs = fixture(); del logs['carol']
        with self.assertRaises(ValueError): self.analyze(manifest, logs)

    def test_broken_sequence_or_unclean_stop_invalidates_evidence(self):
        for change in ['gap','invalid','exit']:
            manifest, logs = fixture()
            if change=='gap': logs['bob'][1]['seq'] = 50
            if change=='invalid': logs['sender'][-1]['fields']['telemetry_valid'] = False
            if change=='exit': manifest['exit_codes']['server'] = 1
            with self.subTest(change=change), self.assertRaises(ValueError): self.analyze(manifest, logs)

    def test_duplicates_do_not_inflate_delivery(self):
        manifest, logs = fixture()
        logs['bob'].insert(-1, copy.deepcopy(logs['bob'][-2]))
        for i,r in enumerate(logs['bob']): r['seq']=i+1
        result = self.analyze(manifest, logs)
        self.assertEqual(result['observed_delivery_fraction'], .5)
        self.assertEqual(result['duplicate_receipts'], 1)

    def test_throughput_uses_only_one_recipient_clock(self):
        manifest, logs = fixture()
        row = copy.deepcopy(logs['bob'][-2]); row['fields'].update(message_id='3', received_ns=1_400_000_000)
        logs['bob'].insert(-1, row)
        for i,r in enumerate(logs['bob']): r['seq']=i+1
        # This fixture has two actually admitted/written messages, unlike the loss case.
        logs['server'] = [r for r in logs['server'] if r['event']!='outbound_not_queued']
        for row in list(logs['server']):
            if row['event'] in ('outbound_enqueued','chat_dequeued','chat_delay_completed','frame_write_completed'):
                new=copy.deepcopy(row); new['fields'].update(message_id='3', origin_request_id=3); logs['server'].insert(-1,new)
        for i,r in enumerate(logs['server']): r['seq']=i+1
        for r in logs['sender']:
            if r['event']=='workload_result': r['fields']['status']='queued'
        result = self.analyze(manifest, logs)
        self.assertEqual(result['bob_mps'], 2)

    def test_missing_server_measurements_cannot_pass_as_success(self):
        manifest, logs = fixture()
        logs['server']=[r for r in logs['server'] if r['event'] not in ('outbound_enqueued','chat_dequeued','chat_delay_completed','frame_write_completed')]
        for i,r in enumerate(logs['server']): r['seq']=i+1
        with self.assertRaises(ValueError): self.analyze(manifest, logs)

    def test_repeated_origin_request_cannot_masquerade_as_multiple_sends(self):
        manifest, logs = fixture()
        for r in logs['server']:
            if r['event']=='route_selected': r['fields']['origin_request_id']=2
        with self.assertRaises(ValueError): self.analyze(manifest, logs)

    def test_fixed_mode_cannot_report_zero_wait_or_inconsistent_arithmetic(self):
        for field,value in [('mode','off'), ('selected_ms',0), ('actual_wait_ns',0), ('queue_only_ns',0)]:
            manifest, logs = fixture()
            for r in logs['server']:
                if r['event']=='chat_delay_completed': r['fields'][field]=value
            with self.subTest(field=field), self.assertRaises(ValueError): self.analyze(manifest, logs)

    def test_clean_process_with_unaccounted_admitted_pair_is_invalid(self):
        manifest, logs = fixture()
        logs['server']=[r for r in logs['server'] if r['event']!='frame_write_completed']
        for i,r in enumerate(logs['server']): r['seq']=i+1
        with self.assertRaises(ValueError): self.analyze(manifest, logs)

    def test_business_identity_chain_rejects_wrong_target_result_origin_or_sender(self):
        for change in ['target','result','origin','sender','mode']:
            manifest, logs = fixture()
            if change=='target':
                for r in logs['sender']:
                    if r['event']=='workload_attempt': r['fields']['target']='carol'
            if change=='result':
                for r in logs['sender']:
                    if r['event']=='workload_result': r['fields']['message_id']='unrelated'
            if change=='origin':
                for r in logs['server']:
                    if 'target_session_id' in r['fields']: r['fields']['origin_request_id']=9999
            if change in ('sender','mode'):
                for r in logs['bob']:
                    if r['event']=='chat_received': r['fields'][change]='stranger' if change=='sender' else 'broadcast'
            with self.subTest(change=change), self.assertRaises(ValueError): self.analyze(manifest, logs)
