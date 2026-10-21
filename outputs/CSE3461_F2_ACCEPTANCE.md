# CSE3461 F2 Local Acceptance Evidence

> Current F3 update (2026-10-21): F3 A implementation was subsequently authorized and completed in the dedicated `feature/f3-delay-jitter` working branch. Earlier skeleton/F2-only restrictions and unimplemented-F3 statements below are historical. See [F3 plan](CSE3461_F3_PLAN.md) and [F3 acceptance](CSE3461_F3_ACCEPTANCE.md) for the current scope and evidence.

2026-10-21 | Implementer verification complete; coordinator independent acceptance pending

Scope: Feature 2 private messaging and required shared publication in the existing framework. **65 automated tests passed**, including all previous protocol/security/lifecycle coverage with obsolete F2-stub expectations updated. A separate actual-server/three-CLI-client localhost demonstration passed **32 checks**. This does not establish real-device over-the-air acceptance or whole-project completion.

## Environment and reproduction

Actual environment: Python 3.14.5, macOS; exact platform, interpreter, commands and all production Python source hashes are in [environment.json](runs/f2-local-20261021-01/environment.json). No third-party runtime dependencies were introduced. Tests bind ephemeral IPv4 loopback ports. The initial sandbox denied local socket binding; approved runs used the normal loopback permission mechanism.

From the repository root:

```sh
python3 -m unittest discover -s tests -t . -v
python3 -m tests.run_private_smoke --output outputs/runs/choose-a-new-f2-directory
python3 -m tests.check_private_mutations
```

The smoke directory must be new; logs are never overwritten by application processes. The mutation command exits 0 only after detecting both deliberate faults. Its displayed FAIL results are expected evidence that the regressions detect the mutations, not failures of the unmodified product.

## Original defects and repair boundary

The coordinator twice exercised standalone `origin/one-one` at `1069ff5a35e4eca1b34ec9d59f63fdaf487ac3fe`: 7/9 checks passed. A 300-byte ASCII body arrived as 195 bytes, and `frag` plus a later `mented` write was treated as two messages. The cause was `recv(200).decode()` being interpreted as a complete message, with no application message boundary. These are coordinator-provided reproductions, not newly rerun standalone evidence in this workflow.

The final product now uses the framework's existing four-byte big-endian length prefix plus UTF-8 JSON. Reads assemble the entire declared payload before decoding or dispatching; the receiver also separates consecutive frames. F2 selection and the shared publisher preserve the complete accepted body. The old branch was **not** fixed, pushed or merged: it remains reference only, and no legacy bare-string entry point is copied into this delivery.

Regression credibility:

- [Original baseline suite](f2_work/baseline-suite.txt): 49/49 passed before implementation.
- [Two focused regressions before implementation](f2_work/private-red.txt): both failed because the F2 path returned an error instead of publishing.
- [Broader pre-implementation tests](f2_work/integration-red.txt): missing handler/publication/capability behavior was exposed.
- [Post-integration suite](f2_work/full-suite.txt): 65/65 passed.
- [Mutation check](f2_work/mutation-check.txt): a 195-character truncation mutation and a one-recv-per-payload mutation each caused their intended assertion to fail. Mutations existed only inside the test process and were restored automatically.

## F2 requirement and regression mapping

| Requirement / failure mode | Evidence | Result |
| --- | --- | --- |
| A03: server-mediated private traffic, third-client isolation, no own echo | `test_300_byte_body_is_complete_and_private`; real CLI smoke including Carol and server route logs | Pass on localhost |
| Original 300-byte truncation | Same named test asserts full body and silence on Alice/Carol; mutation check detects truncation | Pass |
| Original TCP fragmentation | `test_fragmented_body_waits_for_complete_frame`: no response/delivery during a 0.25-second partial frame; exact completed body afterward | Pass |
| Split header / split UTF-8 / merged frames | `test_split_headers_utf8_and_coalesced_frames`; original transport tests retained | Pass |
| Legal larger bodies and over-limit rejection | `test_utf8_byte_limit_and_oversized_frame_rejection`: 4,096 ASCII bytes and 1,024 emoji accepted; 4,097 bytes rejected nonfatally; 65,537 frame header rejected fatally; healthy peers still communicate | Pass |
| A05: missing/self/case-sensitive target and malformed request | `test_bidirectional_errors_and_unavailable_features`; real CLI unknown/self/usage checks | Pass |
| Spoofed sender, invalid types, missing/extra fields, unsafe controls | Same F2 wire test plus retained dispatcher/protocol suite | Pass |
| A06: cleanup and same-name reconnect | `test_reconnect_cannot_receive_old_captured_route`: pauses after lookup, closes Bob, registers new Bob, then releases old route; old admission fails, new traffic succeeds | Pass |
| Bidirectional Unicode and actual client behavior | `test_real_cli_send_receive_errors_and_quit`; three-client actual-process smoke | Pass |
| Concurrent senders / per-sender order | `test_concurrent_senders_preserve_each_sender_order`: Alice and Carol each send 20 messages to Bob concurrently; exact per-sender sequence and 40 unique IDs | Pass |
| Slow recipient queue isolation | `test_full_recipient_queue_does_not_stall_healthy_private_delivery`: one in-flight chat held, 64 actual queue admissions, overflow closes Bob; Carol receives while Bob's writer is still held | Pass, controlled fault fixture |
| Queue admission is not receipt / later write failure | `test_write_failure_after_admission_is_logged_and_isolated`: admitted frame, actual target socket closed before write, failure logged; healthy private traffic succeeds | Pass, controlled fault fixture |
| Shared publisher metadata / counts / invalid route defense | `tests.test_publisher`: body-free logs, captured IDs, same message ID, partial/not_queued counts, invalid private plan rejected before sends, full sender control queue isolated | Pass |
| Implementation vs enablement / F1/F3 boundary | Config, feature and skeleton tests; smoke startup metadata and CLI help | F2 enabled explicitly; default disabled; F1/F3 unimplemented |
| Existing lifecycle and protocol guarantees | All previous 49 tests retained in substance, with obsolete F2 assertions updated; no security/protocol/lifecycle test removed | Pass |
| A04: actual devices over the air | No physical-device run supplied | Pending human/device run |
| A07/A09–A13 and F1 | Outside this work package | Not claimed |

## Final repository verification

After the approved transfer, the suite was rerun **from the actual final repository**:
65/65 passed in 8.104 seconds, [full output](f2_work/final-repository-suite.txt).
A second real-process run from that repository passed all 32 checks:
[final repository smoke summary](runs/f2-finalrepo-20261021-01/smoke-summary.json),
[environment and source hashes](runs/f2-finalrepo-20261021-01/environment.json),
[terminal transcript](runs/f2-finalrepo-20261021-01/terminal-transcript.json).
Source hashes match the reviewed staging run. Current document links resolve and
`git diff --check` passed. The index remains empty and HEAD remains the baseline.

## Actual CLI evidence

The [smoke summary](runs/f2-local-20261021-01/smoke-summary.json) reports `passed=true`, 32 checks and zero exit codes for server, Alice, Bob, Carol and replacement Bob. [Terminal transcript](runs/f2-local-20261021-01/terminal-transcript.json) contains commands and actual output; [server terminal](runs/f2-local-20261021-01/server-terminal.txt) records startup. Five per-process JSONL logs in the same directory have contiguous sequence numbers, final valid-telemetry records and no private message bodies.

Three successful routes are recorded: Alice → Bob (300 characters), Bob → Alice (Chinese), Alice → replacement Bob (new session). Carol receives no private event. Old Bob exits cleanly; a send while absent returns `USER_NOT_FOUND`; replacement Bob sees only the new request. F1/F3 attempts return unavailable errors. Shutdown is exercised while remaining clients wait for input. This is a scripted local CLI run, not a manually supervised course video.

## Review and remaining limits

See [review disposition](f2_work/review.md) and [execution ledger](f2_work/progress.md). The independent implementation review and the coordinator's acceptance are separate checks. Final repository verification is recorded in [final repository suite](f2_work/final-repository-suite.txt) and [import record](f2_work/repository-integration.md).

Only the stated macOS/Python environment and localhost were exercised. Slow-client tests deliberately control writer scheduling for deterministic saturation; they are not Wi-Fi performance measurements. No F3 metric or network-latency claim is made. There is no authentication, encryption, offline storage, resend, global ordering or recipient acknowledgement. `queued` may later be lost to disconnect or write failure. Real-device tests and course deliverables remain manual follow-up, as detailed in the handoff.
