# CSE3461 Framework Acceptance Record

2026-10-21 | Scope: connectable skeleton, plan v1.1 | Native implementation

**S01–S14 passed. Independent final review completed; both Important findings were fixed and regression-tested.** F1/F2, chat publication, and F3 A remain unavailable. These results establish the framework only.

## Environment and evidence

- Actual environment: Python 3.14.5 on macOS; exact OS metadata is in [environment.json](runs/skeleton-smoke-20261021-01/environment.json).
- Automated suite: **49 tests passed**, `python3 -m unittest discover -s tests -t . -v`; [full output](framework_work/final-suite.txt). Some tests contain multiple table-driven cases.
- The execution sandbox initially denied local TCP bind. The identical application subsequently passed with approved loopback permission. This is an environment permission requirement, not a code workaround.
- The supervised run preceded the two final review fixes. The final suite reran all automated acceptance checks and added real CLI quit/EOF-during-registration and malformed-registration logging regressions; no post-fix manual replay is claimed.
- Supervised run: one real server and three concurrent terminal clients on `127.0.0.1:3461`; a fourth client process later replaced Bob after quit. [Captured terminal output](runs/skeleton-smoke-20261021-01/terminal-transcript.json), [computed summary](runs/skeleton-smoke-20261021-01/smoke-summary.json), and five actual process JSONL logs are retained in that directory.
- Fault tests use controlled peers, actual resets/closed log streams, and deliberately accelerated deadline constants. Production registration/partial-frame/request defaults remain 30/5/10 seconds. This record does not imply every automated timeout test waited through the production duration.

## S01–S14 results

| ID | Result | Evidence and observation |
| --- | --- | --- |
| S01 | Pass | Config/argument tests reject invalid host, port, capacity, username and feature enablement with exit 2; occupied listener returns exit 1 without readiness. Both real entry-point help commands ran successfully: [server help](framework_work/server-help.txt), [client help](framework_work/client-help.txt). |
| S02 | Pass | `test_three_clients_with_one_unregistered` plus supervised terminal run: Bob/Alice register while Carol's client waits at the username prompt. Actual local ports and server address appear in captured output. |
| S03 | Pass | Barrier-synchronized duplicate-name unit test produces exactly one winner; live retry returns `USERNAME_TAKEN`, then Carol registers. Wire deadline test preserves original expiry and releases capacity; unregistered capacity is tested. |
| S04 | Pass | Real socket tests split each header boundary and a UTF-8 code point, and concatenate frames. Exactly the intended ordered messages are recovered. |
| S05 | Pass | Protocol/transport tests reject malformed lengths, UTF-8/JSON, duplicate keys, truncated frames and frame expiry. Raw TCP negative cases verify another client can still register. |
| S06 | Pass | Dispatcher tests cover version, direction, unknown type, invalid/reused ID, registration state and spoofed sender. Rejected bodies consume their ID; repeated IDs close with null correlation. Handler spy confirms no unintended business invocation. |
| S07 | Pass | Direct stubs, publisher fixture, raw clients and real CLI all return feature-specific `FEATURE_NOT_IMPLEMENTED`. Supervised logs contain four such rejections (F1 twice, F2 once, F3 once), zero chat events and zero send results. |
| S08 | Pass | Parser tests and supervised CLI reject malformed private input/unknown commands; `/all @literal` reaches the F1 stub; `/help` reports all features unavailable. |
| S09 | Pass | Real CLI shutdown while stdin is blocked, quit before hello, quit with 32 pending requests, quit/EOF while registration is pending, EOF/reset handling, and 16-session bounded shutdown are covered. Supervised server/client processes all exited 0 after orderly quit/shutdown. |
| S10 | Pass | Stale-session cleanup test preserves a new same-name session and cannot redirect old-ID enqueue. Supervised Bob reconnect received a new session ID after the old Bob exited. |
| S11 | Pass | Filling a 64-frame queue rejects the next admission; another connection stays usable. Concurrent producers through one writer preserve complete control frames and per-producer order. Publisher fixture still returns unavailable. |
| S12 | Pass | Requested log-open failure prevents socket startup; runtime log failure stops with exit 1 and invalid-evidence diagnostics. Concurrent JSONL records remain ordered/parseable. Supervised logs have complete lifecycle records and no submitted text bodies. Final regression also confirms rejected nested/oversized usernames and extra registration fields cannot be copied as bodies into JSONL. |
| S13 | Pass — author + independent review | Server starts one receiver/writer per admitted connection. Only the writer calls the server channel's write method. Manager critical sections contain in-memory state and nonblocking queue operations; socket/log work occurs after unlock. Client controller owns writes/pending state, receiver posts events, stdin worker is daemon-only. Capabilities/stubs remain inactive. Independent reviewer confirmed these invariants; two lifecycle/logging findings are resolved as recorded below. |
| S14 | Pass | README commands match actual `--help` and the supervised run. It documents new log paths, limits, unavailable features, interfaces and LAN addressing. All evidence is explicitly labeled localhost; no real-device or F3 result is claimed. |

## Supervised observations

The server accepted Alice, Bob, and a client waiting for a name. The waiting client tried `alice`, received `USERNAME_TAKEN`, then registered as `carol`. Alice submitted broadcast, private and enhancement requests; each received the matching unavailable response. Malformed `@broken` and `/unknown` produced local usage errors. `/all @literal` produced an F1 unavailable response.

Bob quit with a correlated `bye` and exit 0. A new Bob connected successfully with a different session ID. Server Ctrl-C produced unsolicited shutdown byes; Alice, Carol, and the replacement Bob exited 0 without further keyboard input. Peer logs contain no chat event.

All five process logs have increasing contiguous local sequence numbers and final `telemetry_valid=true` records. The server-local interval from the **first shutdown bye enqueue to `process_stopped` was 1.357 ms**. This excludes time between the stop signal and the first enqueue and is not an end-to-end latency result. The separate subprocess tests verify the overall five-second shutdown target. No cross-machine clocks were subtracted.

## Review and limitations

The [independent final review and disposition](framework_work/final-review.md) found no Critical or Minor issues and two Important issues: a registration reply received after quit falsely failed correlation, and invalid registration values could enter logs. Both were reproduced before repair and fixed in one pass. [Failing regressions](framework_work/final-fixes-red.txt) became [passing regressions](framework_work/final-fixes-green.txt); the [final suite](framework_work/final-suite.txt) passed all 49 tests. No second review pass is claimed. There is no unresolved acceptance finding or deferred Minor finding.

Only macOS/Python 3.14.5 and localhost were exercised. Python 3.12 compatibility and Windows/Linux/physical-device operation require actual additional runs. F1/F2 recipient selection and delivery, the common publisher, F3 A delay/jitter and measurements, and course report/video/submissions remain separate work. Passing this matrix does not authorize those stages.
