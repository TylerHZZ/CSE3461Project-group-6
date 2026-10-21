# CSE3461 Framework Handoff

2026-10-21 | Plan v1.1, Native | Skeleton accepted: S01–S14 passed

The connectable framework is implemented and has passed 49 automated tests and a supervised localhost run with three concurrent terminal clients. The delivered scope is real TCP connection/registration, protocol validation, threaded control-message exchange, bounded queues, logging, and cleanup. **F1, F2, shared chat publication, and F3 A remain unimplemented.** Independent review found two Important issues; both were reproduced, fixed and verified by the final full suite. No unresolved acceptance finding remains.

## Run and verify

From the project root, use Python 3.12+ with no third-party dependencies:

```sh
python3 -m cse3461_chat.server --features none
python3 -m cse3461_chat.client --username alice
python3 -m cse3461_chat.client --username bob
python3 -m unittest discover -s tests -t . -v
```

Run server/client commands in separate terminals. Validation used Python 3.14.5 on macOS. See [README](../README.md) for commands, log paths and lifecycle behavior, and the [S01–S14 acceptance record](CSE3461_FRAMEWORK_ACCEPTANCE.md) for exact evidence and limitations.

## Architecture and ownership

**Terminal → client controller → framed IPv4 TCP → server receiver → dispatcher/registration/availability gate → bounded FIFO → single connection writer → client receiver/controller.**

The foundation owns protocol/schema checks, sessions and usernames, threads/queues, IDs, responses, configuration and telemetry. Each server connection has one receiver and one writer; clients never connect directly to one another. The client controller owns state, pending requests, writes and output. F1/F2 remain independent handler modules and must not duplicate foundation responsibilities.

| Integration surface | Import / contract |
| --- | --- |
| F1 | `cse3461_chat.features.broadcast.handle_broadcast(ctx: RequestContext, request: BroadcastRequest) -> FeatureOutcome` |
| F2 | `cse3461_chat.features.private_chat.handle_private(ctx: RequestContext, request: PrivateRequest) -> FeatureOutcome` |
| Shared types | `cse3461_chat.protocol`: `RequestContext`, `BroadcastRequest(text)`, `PrivateRequest(to, text)`, `RoutePlan(recipients)`, `FeatureOutcome`, `AppError(code, message, fatal, feature)` |
| Immutable identity | `cse3461_chat.sessions.SessionView(session_id, username, peer_address)`; no socket |
| Directory | `ctx.directory.find(username) -> SessionView or None`; `ctx.directory.others(origin_session_id) -> tuple[SessionView, ...]` |
| Shared publisher | `cse3461_chat.dispatch.Publisher.publish(ctx, request, plan)` remains unavailable, even with a synthetic plan |

`RequestContext` provides `sender`, `request_id`, `received_ns`, and `directory`. A `RoutePlan` is a nonempty tuple of unique session snapshots. Capture by session ID: disconnect/reuse of a username must not redirect an old request. F1/F2 must not access sockets, create I/O threads, assign message IDs, send responses, or mutate a separate online map.

## Wire agreement for F1/F2

Architecture **v0.2 / wire protocol v1 remains unchanged**. Each frame has a four-byte unsigned big-endian payload length, followed by 1–65,536 UTF-8 JSON bytes. The envelope has exactly `v`, `type`, `request_id`, and `data`. Complete `hello → register → registered` before feature requests.

| Request | `data` | Current result |
| --- | --- | --- |
| `broadcast_send` | `{"text":"Hello"}` | Correlated `error`, `code="FEATURE_NOT_IMPLEMENTED"`, `feature="f1"`, `fatal=false` |
| `private_send` | `{"to":"bob","text":"Hello"}` | Same error with `feature="f2"` |
| `enhancement_request` | `{}` | Same error with `feature="f3"` |

Request IDs strictly increase per connection. Usernames are case-sensitive `[A-Za-z0-9_]{1,24}`. Text is 1–4,096 UTF-8 bytes and is preserved after validation. Clients cannot supply sender identity. All three capability entries remain `implemented=false`, `enabled=false`, `variant=null`; CLI attempts to enable them fail at startup.

Use the [F1/F2 integration brief](CSE3461_F1_F2_INTEGRATION_BRIEF.md) for the complete field/error contract and later routing semantics. For later F1, return other registered recipients or `NO_RECIPIENTS`. For later F2, return exactly the target session or `SELF_TARGET`/`USER_NOT_FOUND`. The foundation owner must implement and verify the common publisher in the same later integration stage. A handler unit test alone does not establish delivery.

## Evidence and next stage

- [Repository import record](framework_work/repository-import.md): preserved source/tests, portable links and fresh repository verification.
- [Final test output](framework_work/final-suite.txt): 49 passing tests, including real CLI quit/EOF during registration and rejected-registration log sanitization.
- [Independent review and fix evidence](framework_work/final-review.md): one review and one verified fix pass; no deferred Minor findings.
- [Acceptance record](CSE3461_FRAMEWORK_ACCEPTANCE.md): S01–S14 with named tests and evidence.
- [Supervised run summary](runs/skeleton-smoke-20261021-01/smoke-summary.json): duplicate-name retry, three clients, all features unavailable, same-name reconnection, and orderly shutdown.
- [Execution ledger](framework_work/progress.md): task checkpoints, red/green outputs and recorded implementation rulings.

Implementation and original acceptance took place in the approved non-Git workspace. The completed files have subsequently been copied into the existing `CSE3461Project-group-6` repository at the user’s request, ready for the user to commit. No commit, push, PR, deployment, third-party dependency or external message was created by this import. Log destinations use exclusive creation, so every process run requires a new path and prior evidence is preserved.

The supervised terminal smoke preceded the two review fixes; the final full suite includes actual-process regressions for the changed lifecycle and TCP logging checks. Validation covers macOS/Python 3.14.5 and localhost only.

## Recorded decisions and practical limits

| Decision | Reason / cost if wrong |
| --- | --- |
| Implement in the approved non-Git workspace and retain file-based evidence | This was the original implementation environment; files are now imported into the existing repository. Git history for this development begins when the user commits. |
| Require new log paths | Protect earlier evidence; repeated runs must select fresh filenames. |
| Keep F1/F2, shared publication and F3 A unimplemented | Preserve the authorized boundary; users cannot exchange chat or run F3 yet. |
| Exclude authentication, encryption, automatic reconnect, heartbeat and delivery receipts | Preserve baseline scope; those guarantees are absent and an idle partition may remain undetected. |
| Claim only the exercised platform/version and localhost | No other environment was tested; compatibility issues may remain undiscovered. |
| Return exit 0 on an orderly server-shutdown bye | Normal protocol termination; callers treating remote shutdown as failure must inspect the reason or adjust policy. |
| Make no experiment/performance conclusion | No F3 experiment exists; workload, baseline/treatment and measurement validation remain necessary. |

The next stage requires separate authorization. F1/F2 must implement their selection logic and the foundation publisher, then demonstrate actual broadcast/private behavior on localhost and real devices. F3 remains option A; its delay/jitter hook, parameters, workload and measurements still require the later design/implementation stage. Team device/Python-minor alignment, course demonstrations, report and submissions remain with the coordinator.
