# F1 integration acceptance evidence

> Coordinator update, 2026-10-21: independent F1/F2/F3 localhost acceptance passed; the merge containing this update integrates F1 into main. See [fresh verification](CSE3461_F1_COORDINATOR_ACCEPTANCE.md). Pending-review and branch-only statements below describe the earlier implementer handoff.

2026-10-21 | Implementer verification complete; independent coordinator acceptance pending.

## Source, environment and result

Actual repository `/Users/nira_def/Documents/GitHub/CSE3461Project-group-6`, branch `feature/f1-broadcast`. Main base `8eee99616500ec9eed92b869a2b5f0544ce78597`; original teammate source `ee35fe66e0a621750148309c0bdea262cdaca5ef`. Exact source ancestry and contribution boundaries are in [handoff](CSE3461_F1_HANDOFF.md) and [provenance](f1_work/provenance.json).

Actual environment: Python 3.14.5/macOS; localhost IPv4 sockets and real subprocesses. Tests target Python 3.12+ but no other version/OS/device was run. Timestamps inside raw logs use UTC and may read October 22; this work date uses the user's America/New_York timezone.

| Verification | Actual result | Evidence |
| --- | --- | --- |
| Exact original teammate snapshot full suite | 69/69 | [original suite](f1_work/original-suite.txt) |
| Independent additional original-source broadcast boundary checks | 6/6 | [extended original checks](f1_work/original-extended.txt) |
| Latest main before integration | 89/89 | [main baseline](f1_work/main-suite.txt) |
| Integrated full suite | 105/105, 15.382 seconds | [full suite](f1_work/full-suite.txt) |
| Final precommit full suite | 105/105, 15.426 seconds | [final suite](f1_work/final-suite.txt) |
| Independent implementation reviewer focused suite | 15/15 | [review record](f1_work/review.md) |
| Actual F1/F2 CLI with F3 off/fixed/jitter | 3/3 conditions, 48 checks each, 87/87 received target pairs | [baseline](f1_work/broadcast-smoke-pilot-02/baseline/checked-summary.json), [fixed](f1_work/broadcast-smoke-pilot-02/fixed/checked-summary.json), [jitter](f1_work/broadcast-smoke-pilot-02/jitter/checked-summary.json) |
| Existing F2 CLI smoke | 32/32 | [summary](f1_work/f2-smoke/smoke-summary.json) |
| Known truncation and one-read framing mutations | Both detected, checker exit 0 | [mutation output](f1_work/mutations.txt) |
| Existing unchanged F3 experiment plus analyzer | 9/9, 540/540 selected target pairs received, no duplicates/unexpected pairs | [runner output](f1_work/f3-experiment.txt), [summary CSV](f1_work/f3-experiment/summary.csv) |
| Successful broadcast and F3 run source/log hashes | All 12 manifests match current source and raw logs | [hash check](f1_work/hash-verification.json) |

Original F1 behavior passed both its own suite and independent added checks. No reproducible original routing bug was found. Its pre-F3 configuration was reconciled with current main; the handler is unchanged. Existing 89 main tests remain in substance; only F1 availability expectations and the F2 test helper's stale capability descriptors were updated. No security/lifecycle coverage was removed.

## Requirement and fault coverage

| Contract / risk | Executed evidence |
| --- | --- |
| All other registered clients, no sender echo, shared ID; unregistered connection excluded | Teammate `test_broadcast_reaches_all_others_without_echo`, actual three-CLI smoke |
| No recipients, disconnected recipients excluded, sender remains usable | Teammate no-recipient test; actual CLI sends after both peers leave |
| Bidirectional broadcast and private isolation | Unicode reverse broadcast; existing F2 smoke; combined-mode private/errors test and CLI checks |
| 300-byte and maximum 4,096-byte bodies; Unicode; split header/payload/UTF-8; coalesced frames | `test_long_unicode_split_header_payload_and_coalesced_frames`; over-byte-limit rejection and retained transport/security tests |
| Two concurrent senders, mixed replies and incoming broadcasts | 12 broadcasts from each sender, two recipients per message; exact IDs and per-sender FIFO checked on both receiving streams; no global ordering assumption |
| Lookup-time session snapshot, later join and same-name reconnect | Handler scheduling gate captures actual directory snapshot, disconnects original Bob and registers replacement/Dave before release; partial result excludes new sessions |
| All captured recipients depart | `not_queued`, selected=2/queued=0/not_queued=2; next broadcast reaches current sessions |
| Slow/full recipient isolation | Actual TCP/64-frame queue with only Bob's socket-write scheduling held; overflow partial=2/1/1, Carol progresses before Bob is released |
| F3 private queue saturation then broadcast | Actual 1,000 ms writer wait, 64 queued private frames; broadcast returns partial=2/1/1; Bob closes/cancels, healthy Carol receives |
| F1+F3 independent streams and FIFO | F1-only with off/fixed/jitter/enabled-zero; 8 broadcasts per run, both recipients checked; distinct jitter streams and actual elapsed wait telemetry |
| Per-recipient cancellation, no replay | Closing Bob cancels his broadcast wait; Carol still receives; new Bob sees no old chat |
| Shutdown cancellation | Both broadcast waits interrupted, two discarded chats counted, bye drains to all clients |
| Capability/config integrity | Eight subsets exercised through real server requests; default disabled; invalid F3 mode/range/duplicate/noncanonical sets rejected |
| F2/F3 regression preservation | Full suite, actual F2 CLI smoke, deliberate framing mutations and unchanged nine-run experiment/analyzer |

Fault fixtures use real sockets/queues and explicit scheduling gates, not simulated successful delivery. They establish deterministic lifecycle/admission behavior; they are not wireless throughput measurements.

## F1/F2/F3 compatibility matrix

Feature names are canonical ascending comma-separated subsets. Default is `none`; all advertise implemented=true, with F3 variant A. A selected F3 requires fixed/jitter mode (including fixed zero); unselected F3 requires off/zero configuration.

| --features | Broadcast | Private | Delay policy |
| --- | --- | --- | --- |
| none | Disabled | Disabled | Off |
| f1 | Enabled | Disabled | Off |
| f2 | Disabled | Enabled | Off |
| f1,f2 | Enabled | Enabled | Off |
| f3 | Disabled | Disabled | Enabled, no chat producer |
| f1,f3 | Enabled | Disabled | Applied to each broadcast recipient |
| f2,f3 | Disabled | Enabled | Applied to private recipient |
| f1,f2,f3 | Enabled | Enabled | Applied to both message modes |

Disabled requests return FEATURE_DISABLED. Enabled `/enhance` returns STARTUP_CONFIG_ONLY; no live configuration change. Unknown/malformed private input never becomes broadcast. Default behavior and F3 numeric/seed constraints are unchanged.

## Actual broadcast measurements and accounting

Each condition starts an actual server CLI and Alice/Bob/Carol CLIs, then replaces Bob. Workload: twelve 256-byte Unicode broadcasts from Alice, one reverse broadcast from Bob, one private Alice→Bob message, one post-reconnect broadcast, private error/usage checks and a no-recipient request. Successful publication therefore selects **28 broadcast target pairs + 1 private pair = 29**, received exactly once. The no-recipient/error requests do not create routes. Checks join `(message_id, session_id)` across route, admission, completed write and actual client `chat_received` events; transcripts additionally confirm complete bodies and no echo/private leakage. Each process exits zero with complete final telemetry.

| Condition | All received pairs | Broadcast wait samples | Selected range ms | Actual wait mean ms | Queue mean ms |
| --- | --- | --- | --- | --- | --- |
| baseline | 29/29 | 28 | 0.000–0.000 | 0.000646 | 0.114877 |
| fixed | 29/29 | 28 | 20.000–20.000 | 23.356588 | 0.102509 |
| jitter | 29/29 | 28 | 6.211–33.935 | 22.222060 | 0.103008 |

Actual waits are measured on the server's monotonic clock around its interruptible wait. Queue residence is separately dequeue minus enqueue. OS scheduling can exceed selected delay; no configured delay substitutes for elapsed time, and no cross-process timestamp subtraction is used. This CLI-paced workload verifies delay integration and observed wait; it does not estimate maximum capacity or compare broadcast versus private throughput. The unchanged nine-run private experiment retains its own analysis/limitations; its first baseline overlapped other regression activity, so its timing is host-load-dependent and is used here for compatibility evidence.

All raw per-process JSONL, transcript, command, source/environment and log hashes reside beside the successful summaries. A manifest's git_head may still show the base because evidence was collected from the resolved merge working tree before its commit; **the recorded per-file source hashes identify the tested content**. They are verified against the delivered source. Earlier original/main baselines refer to their exact stated commits.

## Developmental failures and review

[integration-red](f1_work/integration-red.txt) shows the new subset/capability test rejecting main's absent F1 (four assertion failures and four invalid-config errors). The first merged suite had one failure in a now-obsolete F1-unimplemented assertion in `test_delay`; its raw [output](f1_work/merged-suite.txt) is retained. Updating that status assertion yielded the 105-pass suite.

The first [broadcast smoke capture](f1_work/broadcast-smoke-development.txt) failed its new aggregation code on `session_id`; the established client receipt field is `receiver_session_id`. Product traffic had completed, but those runs are **not** counted as successful evidence. The harness was corrected and three fresh successful runs are under `broadcast-smoke-pilot-02`. The name denotes the second capture, not synthetic data. Original logs were not overwritten. The baseline shell wrapper had a reserved-variable error after tests completed; raw suite output establishes the completed 69/89 tests.

Independent implementation review found no Critical/Important/Minor issues and separately verified source preservation, focused tests and actual pair accounting. [Review scope](f1_work/review.md) distinguishes that review from the coordinator's later acceptance. Existing coordinator acceptance history is preserved unchanged.

## Unverified course scope

No physical-device/over-the-air F1/F2 run, other environment verification, student live video, final report, contribution attestation, sharing permission change or Carmen submission was performed. Localhost terminals do not satisfy the real-device requirement. F1 implementer acceptance does not imply main integration or course completion. Queue admission and even a successful socket write are not recipient receipts; this evidence observes client consumption for these particular runs only.
