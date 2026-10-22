# CSE 3461 Project 1 — Broadcast, Private Messaging and Controlled Delay/Jitter

See the [repository guide](REPOSITORY_GUIDE.md) for feature numbers, branch naming, archived code and document navigation.

A Python standard-library, threaded TCP client/server with **Feature 1 broadcast and Feature 2 private messaging integrated**. It provides registration, strict protocol validation, bounded queues, correlated results, logging and cleanup. **F3 A adds measured application delay/jitter to either message mode.** This is an F1/F2/F3 localhost delivery, not completion of the whole course project.

Independent coordinator acceptance: [historical F2/F3 verification and integration record](outputs/CSE3461_COORDINATOR_ACCEPTANCE.md). F1 integration is delivered on `feature/f1-broadcast` for separate coordinator acceptance; see [F1 evidence](outputs/CSE3461_F1_ACCEPTANCE.md) and [handoff](outputs/CSE3461_F1_HANDOFF.md).

**Provenance:** Aaditya authored the F1 source commit `ee35fe6` on `brodcast-feature`. This integration retains that commit and the broadcast handler unchanged, combines its wiring with current F3, and adds compatibility tests and evidence. This does not assign the integration work to a student. See the handoff for the exact contribution boundary.

## Run locally

Use Python **3.12+** from the repository root; no dependency installation is needed. Actual verification used Python 3.14.5 on macOS. Other versions/devices need their own checks.

Start the server:

```sh
python3 -m cse3461_chat.server --host 127.0.0.1 --port 3461 --features f1,f2
```

Start three clients in separate terminals:

```sh
python3 -m cse3461_chat.client --port 3461 --username alice
python3 -m cse3461_chat.client --port 3461 --username bob
python3 -m cse3461_chat.client --port 3461 --username carol
```

Wait for `[registered]`. Plain text or `/all Hello everyone` from Alice reaches Bob and Carol, without an Alice echo. In Alice's terminal type `@bob Hello Bob`; only Bob receives `[private] alice: Hello Bob`. Carol receives no event and Alice receives a queue result, without her own chat echo. Bob can reply with `@alice 中文回复`. Omit `--username` to prompt after hello; a waiting client does not block other clients.

| Input | Behavior |
| --- | --- |
| `@bob <text>` | Private message to Bob, when F2 is enabled |
| `@missing <text>` | `USER_NOT_FOUND`; no broadcast fallback |
| `@alice <text>` from Alice | `SELF_TARGET` |
| Malformed `@...` or unknown slash command | Local usage error; no request sent |
| Plain text or `/all <text>` | Broadcast to every other registered session when F1 is enabled; `NO_RECIPIENTS` if none |
| `/enhance` | `FEATURE_DISABLED` when F3 is off; `STARTUP_CONFIG_ONLY` when enabled (no live mutation) |
| `/help` | Commands and advertised capabilities |
| `/quit` or stdin EOF | Bounded disconnect/close |

The default remains `--features none`: all three implemented features are disabled and return `FEATURE_DISABLED`. Choose `f1` for broadcast, `f2` for private messages, or `f1,f2` for both. Add `f3` with `--delay-mode fixed` or `jitter` to delay either or both message modes. Hello, registration replies and server startup metadata advertise actual configured capabilities; F1/F2/F3 all have `implemented=true`. F3 has `variant="A"`; others remain null.

Usernames are case-sensitive ASCII letters, digits and underscores, 1–24 characters. The first whitespace after a private target separates target and body; the rest is preserved. Text must contain 1–4,096 **UTF-8 bytes**, cannot be all whitespace and cannot contain unsafe terminal controls. A 300-byte message or a message split across TCP reads is delivered intact. There is no fixed 200-byte message buffer.

`[submitted]` means pending. `[queue result] queued` means the server admitted the event to a recipient queue; **it does not prove receipt or display**. A later write failure or disconnect can discard admitted traffic. `partial` means some broadcast targets admitted the event; `not_queued` means none did. Counts always sum to the lookup-time selected recipient count. A disconnected captured session is not replaced by a later same-name connection; later joiners receive no old broadcast. There are no delivery receipts, automatic retries or offline messages. A same-name reconnect creates a new session and receives no old-session replay.

## Configuration, logs and limits

Both programs accept `--host`, `--port`, `--run-id`, and `--log-file`. The server also accepts `--max-clients` (16 by default, including unregistered connections) and `--features none|f1|f2|f3|f1,f2|f1,f3|f2,f3|f1,f2,f3`; the client accepts `--username`. Run either module with `--help` for all options.

For recorded runs, use a new path for each process:

```sh
mkdir -p outputs/runs/my-f2-run
python3 -m cse3461_chat.server --features f2 --run-id my-f2-run --log-file outputs/runs/my-f2-run/server.jsonl
python3 -m cse3461_chat.client --username alice --run-id my-f2-run --log-file outputs/runs/my-f2-run/alice.jsonl
```

Run those commands in separate terminals. Log files must be new and their parent directory must exist. Requested logging failures stop the affected process and invalidate that run's evidence. Logs contain IDs, routes, queue and lifecycle information, without message bodies. A shared run ID does not synchronize clocks.

| Bound | Default |
| --- | --- |
| Frame / text payload | 65,536 / 4,096 UTF-8 bytes |
| Server outgoing / client event / command queue | 64 frames / 64 events / 16 commands |
| Pending requests | 32 |
| Connect / hello / registration deadline | 5 / 5 / 30 seconds |
| Socket operation timeout / partial-frame deadline | 1 / 5 seconds; fully idle polling is harmless |
| Request timeout | 10 seconds; outcome unknown, no resend |
| Graceful drain / overall shutdown target | 2 / 5 seconds |

Registration retries retain the original deadline. A registration reply timeout closes the connection. Other late replies are labeled late/unmatched. Stop the server with Ctrl-C; clients observe orderly shutdown while waiting for keyboard input. There is no heartbeat, so a silent idle partition is not detected instantly. Exit codes: 0 ordinary quit/orderly shutdown, 2 invalid arguments, 1 runtime/connection/evidence failure.

## Verify and reproduce evidence

```sh
python3 -m unittest discover -s tests -t . -v
python3 -m tests.run_private_smoke --output outputs/runs/my-new-f2-smoke
python3 -m tests.check_private_mutations
python3 -m tests.run_broadcast_smoke --output outputs/runs/my-new-f1-smoke
```

The full suite covers protocol, security, lifecycle, F2 routing and real sockets. The smoke runner starts one real server and three real CLI clients, then replaces Bob after reconnect; it saves transcripts, JSONL logs, environment/source hashes and a checked summary. Its output directory must not already exist. The mutation check deliberately reintroduces truncation and one-recv framing faults **in memory only**: two printed test failures are expected; the tool exits 0 only when both faults are detected. All network checks require loopback bind/connect permission. The broadcast smoke runs actual server/client CLIs under off/fixed/jitter configurations, checks 29 received target pairs per condition, no echo, private isolation, reconnect and no-recipient errors, and saves transcripts, hashes and raw logs.

See [F2 acceptance](outputs/CSE3461_F2_ACCEPTANCE.md) and [F2 handoff](outputs/CSE3461_F2_HANDOFF.md) for the actual results, commands, changed files and remaining manual work. [Original framework acceptance](outputs/CSE3461_FRAMEWORK_ACCEPTANCE.md) remains historical evidence for the earlier 49-test skeleton.

## Feature 3 A: controlled application delay/jitter

The server delays each outgoing **chat** frame in its recipient's sole writer. FIFO and the 64-frame queue remain intact. No wait is directly injected into control replies, but an earlier delayed chat can block later controls on the same connection. F1/F2 queue results still mean admission, never delivery.

```sh
# Zero-delay baseline (F3 disabled)
python3 -m cse3461_chat.server --features f2
# Fixed 20 ms; actual OS elapsed wait may exceed this
python3 -m cse3461_chat.server --features f2,f3 --delay-mode fixed --delay-ms 20
# Uniform selected delay in [5,35] ms
python3 -m cse3461_chat.server --features f2,f3 --delay-mode jitter --delay-ms 20 --jitter-ms 15 --delay-seed 20261021
# Enabled zero-wait control
python3 -m cse3461_chat.server --features f2,f3 --delay-mode fixed --delay-ms 0
```

`delay-ms` is the fixed value or jitter center; `jitter-ms` is the uniform half-width. Both must be finite, with `0 <= jitter <= delay` and `delay+jitter <= 1000` ms. Fixed requires zero jitter; off requires zero delay/jitter. F3 selection requires a fixed/jitter mode and vice versa. Seed is an integer 0..4294967295, default 0. Each recipient has an independent seeded sequence based on username; a reconnect restarts it. Seeds reproduce selected values, not scheduler timing. `--features f3` alone is legal but has no chat producer; enable F1 and/or F2 for broadcast/private traffic. For example, `--features f1,f3 --delay-mode fixed --delay-ms 20` delays broadcasts, and `--features f1,f2,f3` with the same mode delays both. Invalid settings exit 2 before listening.

Closing a session interrupts F3 waits. Interrupted and queued chats are counted as discarded while graceful closure can drain controls/bye. Disabled F3 retains the original drain behavior. Use baseline configuration to turn F3 off; no runtime `/enhance` reconfiguration exists.

Reproduce the nine-run experiment (new directory required):

```sh
python3 -m experiments.run_delay --output outputs/runs/my-new-f3-run
python3 -m experiments.analyze_delay --input outputs/runs/my-new-f3-run
```

The runner starts a real server CLI, a sender using the production client controller, two actual recipient CLIs and an observer CLI. Each condition has 60 private messages of 256 UTF-8 bytes, alternating recipients with target 2 ms spacing, repeated three times. It saves every process log, commands, source hashes, exit statuses and collection outcomes. Analysis checks log completeness before computing rates and failure-inclusive delivery fractions. This measures application scheduling and queueing on localhost, not Wi-Fi propagation or cross-device one-way latency.

See [F3 plan](outputs/CSE3461_F3_PLAN.md), [acceptance](outputs/CSE3461_F3_ACCEPTANCE.md), [measured analysis](outputs/CSE3461_F3_ANALYSIS.md), and [handoff / AI disclosure](outputs/CSE3461_F3_HANDOFF.md).

## Architecture and branch compatibility

`Terminal → client controller → length-prefixed TCP → validation/registration/feature gate → F1/F2 route plan → shared publisher → bounded recipient queue → sole connection writer → client receiver/display`.

The wire format remains four-byte unsigned big-endian length plus strict UTF-8 JSON, protocol v1. The shared manager owns identities and queues; every server connection has one receiver and one writer. Features use immutable session snapshots and the read-only directory. The publisher assigns message IDs, enqueues to captured session IDs and reports queue outcomes. F1 uses that same publisher and selects every other registered, non-closing session in one lookup-time snapshot. No second user registry or socket thread is introduced.

| Location | Responsibility |
| --- | --- |
| `features/private_chat.py` | `handle_private(ctx, request)`: one target or `USER_NOT_FOUND` / `SELF_TARGET` |
| `dispatch.py` | Shared `Publisher` and correlated `send_result` |
| `features/__init__.py` | Explicit binding and capability flags |
| `protocol.py`, `transport.py`, `sessions.py` | Shared types/validation, framing, directory/queue/lifecycle |
| `features/broadcast.py` | F1 snapshot of all other registered sessions or `NO_RECIPIENTS` |
| `features/enhancement.py`, `sessions.py` | F3 writer-local policy, interruptible waits and evidence |

See the [integration brief](outputs/CSE3461_F1_F2_INTEGRATION_BRIEF.md) and [architecture baseline](outputs/CSE3461_ARCHITECTURE_PROPOSAL.md) for exact contracts.

**The standalone `origin/archive/f2-standalone` branch at `1069ff5` is historical reference and still contains the demonstrated framing bugs. It was not repaired or merged.** Its bare-string `server.py` / `client.py` protocol is incompatible with this package. Use only the package entry points above for the integrated product; no duplicate legacy entry point is shipped here.

For future real-device checks, bind the server to its reachable IPv4 address (or `0.0.0.0`) and set each client's `--host` to the server's actual LAN address. Remote clients must not use their own loopback address or `0.0.0.0`. Real-device over-the-air F1/F2 testing, team demonstrations/video, the report and course submission are still pending. F1 coordinator independent acceptance is separate from the implementer checks delivered here. No authentication, encryption, persistent history or public deployment is included.

## Course and team

**CSE 3461 — Computer Networking and Internet Technologies**
The Ohio State University · Autumn 2026

### Team Members

- Luca Sivilotti
- Tianrun Lin
- Aaditya Gupta
- Tyler Zhuangzhuang He

### Team Roles

- **Luca Sivilotti** — Feature
- **Tianrun Lin** — Feature
- **Aaditya Gupta** — Feature
- **Tyler Zhuangzhuang He** — Integration, Debugging, Localhost Testing, and Over-the-Air Testing

Detailed contributions will be recorded separately in `CONTRIBUTIONS.md`. Feature assignments remain subject to team confirmation.
