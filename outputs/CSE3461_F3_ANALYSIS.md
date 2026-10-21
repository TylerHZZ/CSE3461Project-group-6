# F3 A Measured Application Delay/Jitter

2026-10-21 | Final evidence: `outputs/runs/f3-finalrepo-20261021-02`.

Controlled waiting reduced recipient interarrival throughput and increased cumulative queue residence on the existing F2 path. All **540/540** selected recipient-message pairs were observed in the final nine runs. This is a finite localhost observation, not a general reliability guarantee or Wi-Fi latency measurement.

## Workload and evidence

One real server process, a sender process using the production `ClientRuntime`, two actual recipient CLIs (bob/carol), and one actual observer CLI. Each run sends 60 private messages of exactly 256 UTF-8 bytes, alternating recipients: 30 each. Target inter-attempt spacing is 2 ms; the sender awaits each admission result before the next attempt. No warmup messages. All participants register before the controller sends GO. Three repeats use seeds 20261021–20261023. Baseline/fixed/jitter order rotates across repeats.

Baseline: F2 enabled, F3 off. Fixed: F3 enabled, 20 ms selected delay. Jitter: F3 enabled, continuous uniform selected delay in [5,35] ms (center 20, half-width 15). Every recipient owns its own SHA-256(seed:username)-seeded Python Random stream; reconnecting the same username restarts it. Same seeds reproduce selected values in the same runtime and recipient sequence, not OS elapsed waits. The seeds/workload are paired across modes. All selected jitter draws lie inside the configured interval.

[Summary CSV](runs/f3-finalrepo-20261021-02/summary.csv) and [machine-readable summary](runs/f3-finalrepo-20261021-02/summary.json) contain all nine runs and sample counts, including zero failure counts. Each run directory contains manifest, source hashes, actual commands, exit codes, raw sender/server/bob/carol/observer JSONL, server/sender output and client transcripts. [Execution output](f3_work/final-experiment-run.txt) lists all run checks. [Independent arithmetic check](f3_work/independent-calculation.json) recomputes key metrics directly from raw occurrence timestamps without the analyzer helpers; current source hashes match every final manifest.

The controller collects up to 10 seconds after the last queue result, with 0.2 seconds grace after complete reception, then requests server shutdown and allows up to 5 seconds for final closure. Metrics include complete recipient logs through process termination (including any graceful-drain arrivals), not a fabricated exact 10-second window. Normal acceptance additionally requires full receipt before the collection deadline. All final processes exited 0, all normal acceptance checks passed, and no collection timeout occurred. Earlier `f3-finalrepo-20261021-01` data are retained as development evidence; they are not pooled into these results.

## Results

Wait/queue/prewrite columns pool 180 frame samples per mode (60 × 3). Queue p95 uses nearest rank on those raw samples. Rate range covers six separately calculated recipient streams (2 × 3); rates are not summed or averaged into an invented aggregate rate.

| Mode | Actual wait mean (ms) | Queue-only mean (ms) | Queue-only p95 (ms) | Prewrite residence mean (ms) | Recipient rate range (messages/s) | Observed pairs |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| baseline | 0.000223 | 0.074 | 0.103 | 0.131 | 249.95–250.21 | 180/180 |
| fixed | 23.881904 | 292.478 | 572.861 | 316.615 | 40.25–41.34 | 180/180 |
| jitter | 22.129113 | 268.824 | 517.181 | 291.156 | 38.99–50.37 | 180/180 |

Baseline's tiny nonzero measured wait is timing/bookkeeping overhead; it performs no sleep. The configured fixed wait is 20 ms, while measured wait is longer because Event.wait and thread scheduling do not promise exact wake-up timing. The jitter sample mean is not exactly 20 ms in this finite sample. Its selected values and measured waits are separately retained; actual elapsed waits can exceed the selected 35 ms upper bound.

Each recipient is offered approximately 250 messages/s in the baseline workload. That is the workload's offered-rate limit, **not** measured maximum server capacity. With a roughly 20 ms delay before each serialized write, backlog develops in each recipient's own FIFO. Thus queue residence rises across the burst and can greatly exceed the current frame's injected wait. Jitter also causes different short-run rates across recipients. This experiment shows the configured scheduling effect; three short repeats do not establish production capacity, a confidence interval or a general jitter distribution for a network.

## Exact metric and failure definitions

- **Selected wait:** per-frame configured or random value in ms. It is never used as a substitute for elapsed time.
- **Actual injected wait:** `(wait_ended_ns - wait_started_ns)/1e6`, captured around the policy's Event.wait on the server. No directory/log lock is held during this interval. Off/zero has no Event.wait. Completed and cancelled samples have separate counts/distributions; final normal runs have 180 completed and 0 cancelled per mode.
- **Queue-only residence:** `(dequeued_ns - enqueued_ns)/1e6`. The enqueue marker is captured immediately before successful queue put under the manager lock; dequeue is captured immediately after get. Includes prior queued frames' wait/write time, excludes this frame's own policy wait. It includes small queue-operation overhead.
- **Prewrite residence:** `(started_ns - enqueued_ns)/1e6` for the socket write attempt, measured within the server. Includes queue time, current injection, scheduling and instrumentation; it is not pure network latency. CSV reports write-completed samples and excluded selected-pair count. No failed/discarded pair is silently counted as a measured successful write.
- **Recipient interarrival throughput:** `(N-1)*1e9/(last_receive_ns-first_receive_ns)` per recipient, using distinct chat IDs, N>=2, otherwise undefined. `received_ns` is the receiver thread's complete-frame timestamp, emitted as chat_received after controller state validation; no terminal-display time or sender clock is subtracted. This is a finite burst interarrival rate, not whole-run end-to-end throughput or proof of steady state.
- **Observed delivery fraction:** distinct selected `(message_id,target_session_id)` pairs found in recipient logs divided by every selected pair. Queue-full, disconnect, write failure and timeout losses remain in that denominator. Separately show planned/sent/unrouted, admission/write/discard, missing/duplicate/unexpected receipts and received/sent attempt coverage. No-route rejected requests are absent from the route denominator but remain in sent/attempt coverage. Final normal results: 60 planned/sent/selected/admitted/written/received each run, 0 rejected/unrouted/missing/duplicate/unexpected/discarded/write-failed/cancelled.

The analyzer requires all five process logs, exit statuses, contiguous event sequences, lifecycle/telemetry validity and original log hashes. It links attempt index/target → result request/message ID → sent request → route/session → admission/dequeue/wait/write/discard → recipient identity/sender/private mode. It verifies exact terminal accounting, actual timestamp arithmetic, treatment configuration and FIFO. Missing or contradictory evidence fails analysis, never becomes 100%. Valid losses remain measured losses and fail normal acceptance.

## Interpretation and limits

This is application-layer scheduling delay over TCP. TCP retains byte order; the writer deliberately postpones frames while preserving FIFO. Controls have no injected wait but can be blocked behind earlier chat. The queue result is admission only; completed socket write is not receipt. Shutdown cancellation and full-queue loss are covered in separate fault tests, not hidden in these successful normal runs.

All raw timing subtraction occurs inside one process. A shared run ID and UTC strings do not synchronize device clocks. No cross-device one-way latency, radio propagation, physical-device test, retransmission comparison or reliability improvement is claimed. Only Python 3.14.5/macOS localhost was exercised; Python 3.12+ remains the supported target requiring separate version/platform checks. Synthetic messages and five concurrent processes are a small educational workload.

AI assisted with planning, implementation, test construction, orchestration and analysis; see the [actual contribution statement](CSE3461_F3_HANDOFF.md). No student contribution, final report, video or course submission is fabricated.
