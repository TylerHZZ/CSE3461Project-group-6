# Feature 3 A Implementation Plan

> For agentic workers: use superpowers:executing-plans inline and test-driven-development. The explicit F3 execution authorization supersedes earlier skeleton-only restrictions and intermediate approval/commit steps. Do not commit or push.

**Goal:** Demonstrate controlled application delay/jitter on the working F2 TCP path with reproducible, measured localhost evidence.

**Architecture:** Preserve one bounded FIFO and sole writer per recipient. Apply a local delay policy immediately before chat writes, outside directory and telemetry locks. Control frames have no injected wait but can remain behind earlier chats. No wire schema changes or F1 implementation.

**Tech stack:** Python 3.12+ standard library, existing threaded TCP and length-prefixed JSON.

**Spec:** Architecture proposal sections 10–11 plus this authorized design refinement. Baseline final repository `64a0459`; clean export in `f3-stage`, never the old workspace code. Final import uses baseline hashes and clean git checks.

## Design and constraints

- CLI: `--features none|f2|f3|f2,f3`; default none. F3 is implemented with variant `A` even when disabled. F1 stays unimplemented. `--delay-mode off|fixed|jitter` defaults off; F3 selection requires fixed/jitter, and these modes require F3 selection. F3 alone is legal but has no implemented chat producer until F2 is also enabled.
- `--delay-ms` center/fixed delay defaults 0; `--jitter-ms` half-width defaults 0; finite numeric values with 0 <= jitter <= delay and delay+jitter <= 1000 ms. Fixed requires jitter=0; off requires both=0. `--delay-seed` defaults 0, integer 0..2^32-1. Reject invalid values before listening (CLI exit 2). Enabled fixed 0 is a valid zero-wait control.
- Uniform continuous jitter on [delay-jitter, delay+jitter]. Each recipient writer owns `random.Random` seeded by SHA-256 of `seed:username` (UTF-8, digest interpreted as big-endian integer). Same username/new session restarts sequence; UUID/scheduling do not affect draws. Reproducing selected delays requires same username, config and per-recipient chat sequence, same supported Python implementation; measured wall time is not reproducible exactly.
- `DelayPolicy.before_chat_write(cancel: Event) -> WaitObservation` returns selected milliseconds, start/end monotonic nanoseconds and cancellation flag. One policy per session, lazily created on first chat. Off/zero performs no sleep. Only chat calls this method.
- Session close signals cancellation. With F3 enabled, interrupted in-flight and queued chats are discarded and counted; graceful close can drain existing controls/bye. Disabled mode retains original drain behavior. No new queue or retry. A disconnect/write race remains possible as in any socket application; queue admission is never receipt.
- Timestamp successful queue insertion immediately before put while holding the existing brief manager lock. Record dequeue, wait start/end, write start/end. Wait executes outside all locks. Log `chat_delay_completed` for every dequeued chat, including zero/off and cancelled attempts. No bodies.
- `/enhance` does not mutate a live policy or start an experiment. Disabled returns FEATURE_DISABLED; enabled returns nonfatal STARTUP_CONFIG_ONLY explaining transparent startup behavior. No fake successful run/status response or new protocol type.

## Review focus

1. Control behind chat: test same-queue FIFO and demonstrate indirect delay.
2. Shutdown during wait: test prompt cancellation, discarded count, no delayed write, clean exit.
3. Queue saturation with F3: fill real queue while writer waits, preserve not_queued and healthy-recipient progress.
4. Unreproducible seeds: test repeatability by username and independent streams despite interleaving.
5. Missing/corrupt logs: analyzer must reject incomplete evidence, never silently report 100%.

## Tasks and verification

- [x] T1 Config/policy/capabilities: add failing tests in `tests/test_delay.py`; implement `features/enhancement.py`, config fields/parser, bindings, commands help and runtime wiring. Keep the enhancement request in the existing error-response contract. Check invalid finite/range/type/mode combinations, seed streams, enabled/disabled/zero. Update only superseded F3 expectations in existing tests and smoke runner.
- [x] T2 Writer integration: add meaningful socket tests for chat-only delay, FIFO, independent recipients, cancellation, full queue, telemetry and log failure. Modify `sessions.py` and `server.py`; preserve queue capacity 64 and correlation. Full suite must pass with all F2 framing, Unicode, isolation, reconnect tests retained.
- [x] T3 Experiment and analyzer: `experiments/run_delay.py` starts actual server CLI plus actual client CLIs (sender, bob, carol, observer), one fresh directory per scenario/repeat. `experiments/analyze_delay.py` validates complete logs and joins route/message/session IDs. Add hand-calculated fixture tests for failure denominators, duplicates/missing logs and local-clock metrics. Run actual experiments only after tests pass.
- [x] T4 Delivery: update current README/framework/integration status and historical annotations; create F3 handoff, acceptance, analysis and AI disclosure. Fresh review, hash-guarded import to final repository with normal permission request, then full suite, F2 smoke and nine F3 experiments from that location. Produce a clean local source archive, no credentials/caches/irrelevant workspace files. No stage/commit/push.

## Experiment protocol

Primary comparison: baseline (`features f2`, off), fixed (`features f2,f3`, fixed 20 ms), jitter (`features f2,f3`, center 20 ms, half-width 15 ms). Three repetitions, seeds 20261021, 20261022, 20261023, same seed for matched conditions. Connect sender, bob, carol, observer; wait for all registrations. Send 60 messages of exactly 256 UTF-8 bytes, alternating bob/carol, at a target interval 2 ms. Use sender CLI, wait for each queue result before the next command to avoid pending-command overload; record actual sent timestamps and interval, so pacing slippage is visible. Each recipient expects 30. No warmup traffic. Baseline/treatment order rotates each repetition to reduce fixed-order bias.

After final send, collect for up to 10 seconds for 60 matching chat events (or errors); on full reception allow 0.2 seconds observation grace. On deadline retain every attempt and all failures. Then SIGTERM server, wait up to 5 seconds and collect all client final logs. Timeout, forced kill, nonzero exits, missing logs or invalid telemetry mark evidence invalid; valid complete logs with delivery loss remain valid measurements of loss, not automatically successful acceptance. Retain manifest, server terminal, CLI transcript, raw sender/server/recipient/observer JSONL and collection outcome. No remote device/network claim.

## Metrics and acceptance

All durations subtract timestamps from one process only, in milliseconds unless stated otherwise:
- Actual injection wait: wait-end minus wait-start around Event.wait; selected delay reported separately. Include cancelled samples separately, never replace actual with configured delay.
- Queue-only residence: dequeue minus successful enqueue marker. Prewrite residence: socket write-start minus enqueue, includes this frame's injection plus prior queueing. Report N, mean, p50, p95 (nearest rank), min/max; no write-start exists for discarded frames, report excluded sample count explicitly.
- Recipient steady-stream throughput: (N-1)/(last_receive-first_receive), messages/s, per recipient, N>=2; not total workload throughput or sender-to-recipient latency.
- Observed delivery: distinct (message_id,target_session_id) received / all selected target pairs, including queued failures and write failures. Separately report planned=60, sent, rejected/unrouted, admitted, writes, received, duplicate/unexpected, missing. Recipient-log completeness is required, never inferred from missing files. Attempt coverage uses received/sent for this one-target workload and shows rejected requests too.
- Sender request-to-result time: optional local send/response correlation; this is queue acknowledgement latency only.

Acceptance: all baseline/regression tests pass; complete nine-run evidence, matched workload and 60/60 observed for each normal comparison; injected means/ranges and reduced recipient throughput explained honestly; no private events to sender/observer; measured wait cancellation and full queue tests pass. OS scheduling can overshoot configured delay bounds, so actual elapsed bounds are descriptive, not hard timing assertions.

Rollback: disable F3 using `--features f2 --delay-mode off` and default zero numeric values. Code rollback consists only of this change's listed files, preserving later edits; no reset/clean command. The final handoff provides changed-file inventory and source hashes.

## Execution refinements (recorded, not retrospective result assumptions)

- User steering required the GitHub branch before implementation. Created `feature/f3-delay-jitter` at existing remote baseline 64a0459, set upstream, and implemented directly in the final checkout on that branch with approved write permissions. No unfinished code was committed/pushed. The preparation export contains only initial plan/baseline work and is not the product source.
- Inspection found terminal input polling could cap the intended offered load. Sender uses the existing `ClientRuntime` in a small separate process; recipient and observer processes use the actual CLI. Sender waits for each queue result and targets 2 ms inter-attempt spacing; every send time is logged. This changes the harness, not the wire protocol or client controller.
- The existing client had generic response events but lacked the design's explicit `chat_received` event. Added it after state validation, carrying the original receiver-thread frame completion timestamp, session/message IDs and byte length, without text. This is application consumption evidence, not proof of terminal display.
