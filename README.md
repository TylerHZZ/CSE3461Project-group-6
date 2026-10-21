# CSE 3461 Project 1 — Connectable Framework

A standard-library, threaded TCP client/server **skeleton**. It supports real connections, registration, protocol validation, concurrent control traffic, logging, and cleanup. **F1 broadcast, F2 private delivery, the chat publisher, and F3 A are intentionally unimplemented.** Valid feature requests return `FEATURE_NOT_IMPLEMENTED`; they do not send chat messages or successful send results.

## Run locally

Use Python **3.12+** from this project directory. No dependency installation is needed. Validation on this workstation uses Python 3.14.5 on macOS; other versions/devices are not claimed as tested.

Start the server in one terminal:

```sh
python3 -m cse3461_chat.server --host 127.0.0.1 --port 3461 --features none
```

Start a client in each additional terminal:

```sh
python3 -m cse3461_chat.client --port 3461 --username alice
python3 -m cse3461_chat.client --port 3461 --username bob
python3 -m cse3461_chat.client --port 3461
```

The last client prompts for a username after hello. A client waiting at this prompt does not block the others. Usernames are case-sensitive ASCII letters, digits, and underscores, 1–24 characters. Each client displays its actual local endpoint and server endpoint. A TCP connection is not registration success; wait for `[registered]`.

| Input | Skeleton behavior |
| --- | --- |
| Plain text or `/all <text>` | F1 unavailable error |
| `@bob <text>` | F2 unavailable error; no private delivery |
| `/all @literal` | Explicit F1 request with literal leading `@` |
| `/enhance` | F3 unavailable error; no delay injection |
| `/help` | Local command and capability information |
| `/quit` or stdin EOF | Bounded disconnect/close |
| Malformed `@...` or unknown slash command | Local usage error; no request sent |

The first whitespace after a private target separates the target from the body; the remaining body is preserved. Text must contain 1–4,096 UTF-8 bytes and cannot be all whitespace. Unsafe terminal controls are rejected/escaped. `[submitted]` means pending, not delivered. The skeleton never reports chat delivery.

Stop the server with Ctrl-C. Connected clients observe shutdown even when waiting for keyboard input. A silent idle network partition is not detected instantly: there is no heartbeat. Reconnect explicitly by starting a new client; no request is replayed automatically.

## Configuration and evidence

Both entry points accept `--host`, `--port`, `--run-id`, and `--log-file`. Server options also include `--max-clients` (default 16, counting unregistered connections) and `--features` (only `none` is accepted). The client accepts optional `--username`. Run either module with `--help` for the complete argument list.

To record an actual run, choose a fresh directory and a different log file per process:

```sh
mkdir -p outputs/runs/local-01
python3 -m cse3461_chat.server --run-id local-01 --log-file outputs/runs/local-01/server.jsonl
python3 -m cse3461_chat.client --username alice --run-id local-01 --log-file outputs/runs/local-01/alice.jsonl
```

Run the client command in another terminal while the server is running. **Log files must be new; existing files are not overwritten.** Their parent directory must exist. A requested logging failure stops the affected process with an error and invalidates that run's evidence. Without `--log-file`, no log file is created. Logs contain correlation IDs and lifecycle information, not message bodies. A shared `--run-id` is a label; it does not synchronize clocks.

| Bound | Default |
| --- | --- |
| Frame / text payload | 65,536 / 4,096 UTF-8 bytes |
| Outgoing server queue / client event queue / command queue | 64 frames / 64 events / 16 commands |
| Pending requests | 32 |
| Connect / hello / registration deadline | 5 / 5 / 30 seconds |
| Socket operation timeout / partial-frame deadline | 1 / 5 seconds; fully idle polling is harmless |
| Request timeout | 10 seconds; outcome unknown, no resend |
| Graceful drain / overall shutdown target | 2 / 5 seconds |

Registration retries do not reset the acceptance-time deadline. A registration-reply timeout closes the connection; other late replies are labeled late/unmatched without changing completed request state. Exit codes are 0 for ordinary quit or orderly server shutdown, 2 for invalid arguments, and 1 for runtime/connection/evidence failure.

For later LAN verification, bind the server to its reachable IPv4 address (or explicitly to `0.0.0.0`) and point clients at the server's actual LAN address. Remote clients must not use `0.0.0.0` or their own loopback address. LAN configuration is supported; actual device/network compatibility needs its own verification. Several local terminals are not a real-device demonstration.

## Architecture and feature handoff

`Terminal → client controller → length-prefixed TCP → server receiver → validation/registration/feature gate → bounded control queue → sole connection writer → client receiver → controller/display`.

Each server connection has one receiver and one writer thread. The session manager owns names, identity snapshots, queues, and closing state. The client main thread owns protocol state, pending requests, writes, and terminal output; a receiver posts network events and a daemon worker reads stdin.

| Location | Public integration surface |
| --- | --- |
| `cse3461_chat.protocol` | `RequestContext`, `BroadcastRequest`, `PrivateRequest`, `RoutePlan`, `FeatureOutcome`, `AppError`, shared message/result types |
| `cse3461_chat.sessions` | Immutable `SessionView`; read-only `Directory.find(username)` and `Directory.others(origin_session_id)` |
| `cse3461_chat.features.broadcast` | `handle_broadcast(ctx, request)` — stub |
| `cse3461_chat.features.private_chat` | `handle_private(ctx, request)` — stub |
| `cse3461_chat.features.enhancement` | `handle_enhancement(ctx, request)` — stub |
| `cse3461_chat.dispatch` | `Publisher.publish(ctx, request, plan)` — stub, including direct fixture calls |

F1/F2 developers own their handler module and feature tests. They must not send frames, create I/O threads, maintain a second user map, generate message IDs, or modify common schemas independently. A later integration stage must implement the shared publisher as well as the handlers. Selected F3 A introduces no active writer hook or experiment here. Capabilities remain `implemented=false`, `enabled=false`, `variant=null` for all three features.

The wire format is a four-byte unsigned big-endian length followed by a strict UTF-8 JSON object with exactly `v`, `type`, `request_id`, and `data`. Protocol version is 1. See the [architecture baseline](outputs/CSE3461_ARCHITECTURE_PROPOSAL.md) and [F1/F2 integration brief](outputs/CSE3461_F1_F2_INTEGRATION_BRIEF.md) for exact payloads, validation order, and error semantics.

## Verify

```sh
python3 -m unittest discover -s tests -t . -v
```

Tests use temporary local ports, controlled stream peers, actual threads, and real client subprocesses. They need permission to bind/connect on loopback. Some fault tests intentionally close logs, reset sockets, or accelerate deadlines; these are labeled fixtures, not feature demonstrations or F3 measurements.

The [framework acceptance record](outputs/CSE3461_FRAMEWORK_ACCEPTANCE.md) maps S01–S14 to evidence. The [English handoff](outputs/CSE3461_FRAMEWORK_HANDOFF.md) describes the delivered boundary and remaining work. No GUI, persistent chat history, automatic retry/reconnect, active business feature, performance experiment, or real-device course demonstration is included.

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
