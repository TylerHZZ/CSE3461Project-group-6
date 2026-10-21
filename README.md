# CSE 3461 Project 1 — Framework with Private Messaging

See the [repository guide](REPOSITORY_GUIDE.md) for feature numbers, branch naming, archived code and document navigation.

A Python standard-library, threaded TCP client/server with **Feature 2 private messaging integrated**. It provides registration, strict protocol validation, bounded queues, correlated results, logging and cleanup. **F1 broadcast and F3 A remain unimplemented.** This is an F2 implementation and localhost delivery, not completion of the whole course project.

## Run locally

Use Python **3.12+** from the repository root; no dependency installation is needed. Actual verification used Python 3.14.5 on macOS. Other versions/devices need their own checks.

Start the server:

```sh
python3 -m cse3461_chat.server --host 127.0.0.1 --port 3461 --features f2
```

Start three clients in separate terminals:

```sh
python3 -m cse3461_chat.client --port 3461 --username alice
python3 -m cse3461_chat.client --port 3461 --username bob
python3 -m cse3461_chat.client --port 3461 --username carol
```

Wait for `[registered]`. In Alice's terminal type `@bob Hello Bob`; only Bob receives `[private] alice: Hello Bob`. Carol receives no event and Alice receives a queue result, without her own chat echo. Bob can reply with `@alice 中文回复`. Omit `--username` to prompt after hello; a waiting client does not block other clients.

| Input | Behavior |
| --- | --- |
| `@bob <text>` | Private message to Bob, when F2 is enabled |
| `@missing <text>` | `USER_NOT_FOUND`; no broadcast fallback |
| `@alice <text>` from Alice | `SELF_TARGET` |
| Malformed `@...` or unknown slash command | Local usage error; no request sent |
| Plain text or `/all <text>` | F1 `FEATURE_NOT_IMPLEMENTED` |
| `/enhance` | F3 `FEATURE_NOT_IMPLEMENTED` |
| `/help` | Commands and advertised capabilities |
| `/quit` or stdin EOF | Bounded disconnect/close |

The default server option remains `--features none`: F2 is implemented but disabled and returns `FEATURE_DISABLED`. `--features f2` enables it. Requests to enable F1/F3 are rejected at startup. Hello, registration replies and server startup metadata use the actual handler capability snapshot. F1/F3 advertise `implemented=false, enabled=false`; F2 advertises `implemented=true` and its configured enablement. All variants remain null.

Usernames are case-sensitive ASCII letters, digits and underscores, 1–24 characters. The first whitespace after a private target separates target and body; the rest is preserved. Text must contain 1–4,096 **UTF-8 bytes**, cannot be all whitespace and cannot contain unsafe terminal controls. A 300-byte message or a message split across TCP reads is delivered intact. There is no fixed 200-byte message buffer.

`[submitted]` means pending. `[queue result] queued` means the server admitted the event to a recipient queue; **it does not prove receipt or display**. A later write failure or disconnect can discard admitted traffic. `not_queued` means the captured recipient could not accept the event. There are no delivery receipts, automatic retries or offline messages. A same-name reconnect creates a new session and receives no old-session replay.

## Configuration, logs and limits

Both programs accept `--host`, `--port`, `--run-id`, and `--log-file`. The server also accepts `--max-clients` (16 by default, including unregistered connections) and `--features none|f2`; the client accepts `--username`. Run either module with `--help` for all options.

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
```

The full suite covers protocol, security, lifecycle, F2 routing and real sockets. The smoke runner starts one real server and three real CLI clients, then replaces Bob after reconnect; it saves transcripts, JSONL logs, environment/source hashes and a checked summary. Its output directory must not already exist. The mutation check deliberately reintroduces truncation and one-recv framing faults **in memory only**: two printed test failures are expected; the tool exits 0 only when both faults are detected. All network checks require loopback bind/connect permission.

See [F2 acceptance](outputs/CSE3461_F2_ACCEPTANCE.md) and [F2 handoff](outputs/CSE3461_F2_HANDOFF.md) for the actual results, commands, changed files and remaining manual work. [Original framework acceptance](outputs/CSE3461_FRAMEWORK_ACCEPTANCE.md) remains historical evidence for the earlier 49-test skeleton.

## Architecture and branch compatibility

`Terminal → client controller → length-prefixed TCP → validation/registration/feature gate → F2 route plan → shared publisher → bounded recipient queue → sole connection writer → client receiver/display`.

The wire format remains four-byte unsigned big-endian length plus strict UTF-8 JSON, protocol v1. The shared manager owns identities and queues; every server connection has one receiver and one writer. Features use immutable session snapshots and the read-only directory. The publisher assigns message IDs, enqueues to captured session IDs and reports queue outcomes. It also preserves the shared broadcast publication contract for future F1 integration; no F1 routing is enabled.

| Location | Responsibility |
| --- | --- |
| `features/private_chat.py` | `handle_private(ctx, request)`: one target or `USER_NOT_FOUND` / `SELF_TARGET` |
| `dispatch.py` | Shared `Publisher` and correlated `send_result` |
| `features/__init__.py` | Explicit binding and capability flags |
| `protocol.py`, `transport.py`, `sessions.py` | Shared types/validation, framing, directory/queue/lifecycle |
| `features/broadcast.py`, `features/enhancement.py` | F1/F3 extension stubs |

See the [integration brief](outputs/CSE3461_F1_F2_INTEGRATION_BRIEF.md) and [architecture baseline](outputs/CSE3461_ARCHITECTURE_PROPOSAL.md) for exact contracts.

**The standalone `origin/archive/f2-standalone` branch at `1069ff5` is historical reference and still contains the demonstrated framing bugs. It was not repaired or merged.** Its bare-string `server.py` / `client.py` protocol is incompatible with this package. Use only the package entry points above for the integrated product; no duplicate legacy entry point is shipped here.

For future real-device checks, bind the server to its reachable IPv4 address (or `0.0.0.0`) and set each client's `--host` to the server's actual LAN address. Remote clients must not use their own loopback address or `0.0.0.0`. Real-device over-the-air testing, team demonstrations/video, F1/F3, the report and course submission are still pending. No authentication, encryption, persistent history or public deployment is included.

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
