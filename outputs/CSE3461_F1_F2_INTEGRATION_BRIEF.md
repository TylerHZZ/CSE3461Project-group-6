# CSE3461 | Feature 1 / Feature 2 Integration Brief

Version 1.3 (F2/F3 integrated; protocol unchanged) | 2026-10-21 | Based on `CSE3461_ARCHITECTURE_PROPOSAL.md` v0.2; wire protocol v1.

**Current status: F2 and shared publication are implemented and locally verified. F1 remains unimplemented; F3 A is available through startup delay configuration. See [F3 handoff](CSE3461_F3_HANDOFF.md).** Use `--features f2`; default `none` disables F2. See [F2 acceptance](CSE3461_F2_ACCEPTANCE.md) and [F2 handoff](CSE3461_F2_HANDOFF.md). Earlier skeleton evidence is historical.

## 1. Architecture and ownership

**Current: terminal client → framed TCP → registration/validation/feature gate → F2 recipient plan → shared publisher → recipient queue/writer → receiving client.** Control replies use the same per-connection queue. F1 recipient planning is still a stub.

Baseline: Python 3.12+ standard library, IPv4 TCP, one receiver thread and one writer thread with a bounded FIFO per server connection. Clients never connect directly to each other.

| Owner | Deliverable and boundary |
| --- | --- |
| Foundation | Protocol/validation, connections/registration, online directory, dispatch, queues, threads, logs, and client commands; shared chat publication (now implemented) |
| F1 | Broadcast handler in `cse3461_chat/features/broadcast.py` and its tests; select recipients or return an error |
| F2 | Private-message handler in `cse3461_chat/features/private_chat.py` and its tests; select one recipient or return an error |

F1/F2 **must not access sockets, maintain separate online-user maps, create I/O threads, generate message IDs, or send responses**. If an existing independent application uses different interfaces, report the differences and coordinate an adapter. Do not merge incompatible private protocols. F3 A now introduces configured delay/jitter in the shared writer path; F1/F2 must not add their own waits or change message formats.

## 2. F1/F2 function contracts

Entry-point signatures; F1 remains a stub and F2 now implements the recipient contract:

```text
handle_broadcast(ctx: RequestContext, request: BroadcastRequest) -> FeatureOutcome
handle_private(ctx: RequestContext, request: PrivateRequest) -> FeatureOutcome
```

| Shared type | Required fields / invariant |
| --- | --- |
| `RequestContext` | `sender:SessionView`, `request_id:int`, `received_ns:int`, `directory:Directory` |
| `SessionView` | `session_id:str`, `username:str`, `peer_address:tuple[str,int]`; immutable snapshot, no socket |
| `BroadcastRequest` / `PrivateRequest` | Broadcast: `text:str`; private: `to:str`, `text:str` |
| `RoutePlan` | `recipients:tuple[SessionView,...]`; nonempty, unique session IDs |
| `AppError` | `code:str`, `message:str`, `fatal:bool`, `feature`: `"f1"`, `"f2"`, `"f3"`, or null; each handler uses its own feature ID |
| `FeatureOutcome` | `RoutePlan` or `AppError`; never custom JSON, sockets, or a bare recipient list |

Import shared request/result/context types from `cse3461_chat.protocol`; import `SessionView` and `Directory` from `cse3461_chat.sessions`. Entry points are `cse3461_chat.features.broadcast.handle_broadcast` and `cse3461_chat.features.private_chat.handle_private`. The foundation provides shared types; do not redefine them inside feature modules. Normal dispatch invokes a feature only after common validation, successful registration, and implementation/enablement checks.

| Feature | Directory API | Required result |
| --- | --- | --- |
| F1 broadcast | `ctx.directory.others(ctx.sender.session_id)` returns a tuple snapshot of other registered, non-closing sessions | Nonempty: wrap in `RoutePlan`. Empty: return `AppError` with `code="NO_RECIPIENTS"`, `fatal=false`, `feature="f1"`, and an explanatory message |
| F2 private | `ctx.directory.find(request.to)` returns `SessionView` or `None` | Own username: `SELF_TARGET`. Missing target: `USER_NOT_FOUND`. Otherwise: a one-recipient `RoutePlan`. Both errors have `fatal=false`, `feature="f2"`, and an explanatory message |

Handlers can run concurrently for different clients. Use request-local data and the shared read-only directory; keep no mutable global state. Capture recipients by **session ID**: a later connection reusing the username must not receive an old request. Broadcast membership is a lookup-time snapshot; later joiners receive no replay. Preserve each sender's order to a recipient; no global order across senders is promised.

## 3. Wire format and client interaction

- Frame: **four-byte unsigned big-endian payload length + UTF-8 JSON object**. Payload length excludes the header and is 1–65,536 bytes. One receive call is not necessarily one message.
- Exact envelope keys: `v`, `type`, `request_id`, `data`; `v=1`. Client request IDs strictly increase per connection, range 1–9,007,199,254,740,991. Replies echo the ID; unsolicited server events use null. A valid new ID is consumed even if later checks reject the request.
- Usernames are case-sensitive `[A-Za-z0-9_]{1,24}`. Text is 1–4,096 UTF-8 bytes, not all whitespace; only tab/newline control characters are allowed. Preserve accepted text.
- Reject extra fields, duplicate JSON keys, non-finite numbers, and incorrect types; booleans are not integers. Derive sender identity from registration; clients cannot supply `sender`.
- Complete `hello → register → registered` before feature requests. Default endpoint: `127.0.0.1:3461`; remote clients use the server's actual LAN address. Registration deadline: 30 seconds.
- Defaults: 16 connections including unregistered ones; 64 outbound frames per connection. A request timeout after 10 seconds means outcome unknown, with no automatic resend. A registration-reply timeout closes the connection. These are project defaults, not course requirements.

All payload fields below are required. `Features` contains `f1/f2/f3`, each with `implemented:boolean`, `enabled:boolean`, and `variant:string or null`. SessionId and MessageId are server-generated canonical lowercase UUID strings.

| `type` | Direction | `data` |
| --- | --- | --- |
| `hello` | Server → client, unsolicited | `session_id`, `registration_required:true`, `max_frame_bytes:65536`, `max_text_bytes:4096`, `registration_timeout_s:number`, `features:Features` |
| `register` | Client → server | `username:string` |
| `registered` | Server → client, reply | `session_id`, `username:string`, `features:Features` |
| `broadcast_send` | Client → server | `text:string` |
| `private_send` | Client → server | `to:string`, `text:string` |
| `chat_message` | Server → recipient, unsolicited | `message_id`, `mode`: `"broadcast"` or `"private"`, `sender:string`, `recipient:string or null`, `text:string` |
| `send_result` | Server → sender, reply | `message_id`, `status`, `selected_count:int`, `queued_count:int`, `not_queued_count:int`; semantics below |
| `error` | Server → client | `code:string`, `message:string`, `fatal:boolean`, `feature`: `"f1"`, `"f2"`, `"f3"`, or null |
| `disconnect` / `bye` | Client request / server reply or shutdown notification | Request: `{}`. Reply: `reason`: `"client_request"` or `"server_shutdown"` |

Request examples (JSON payloads only; binary length headers omitted):

```json
{"v":1,"type":"broadcast_send","request_id":2,"data":{"text":"Hello everyone"}}
```

```json
{"v":1,"type":"private_send","request_id":3,"data":{"to":"bob","text":"Only for Bob"}}
```

Commands: plain text or `/all <text>` → F1; `@bob <text>` → F2; `/quit` → disconnect. Split private input at the first whitespace after the target, remove the separating whitespace, and preserve the remaining body. Malformed `@...` input must show a usage error, never fall back to broadcast. Use `/all @...` to broadcast literal text beginning with `@`.

## 4. Publication, responses, and errors

**Implemented shared contract:** the dispatcher calls `cse3461_chat.dispatch.Publisher.publish(ctx, request, plan) -> PublishResult | AppError`; feature handlers must not. The publisher is constructed with the existing SessionManager, assigns a UUID, validates the recipient plan, builds a chat event and attempts each captured session queue. The dispatcher emits the correlated `send_result`. Future broadcast plans use the same shared implementation; the F1 handler and availability gate remain unimplemented.

- **F1:** send the same message ID to every captured recipient; `mode="broadcast", recipient=null`. The origin receives only a control response, not its own chat event.
- **F2:** send to exactly the captured target; `mode="private", recipient=<target username>`. Bystanders receive neither the body nor a private-message notification. Missing targets never trigger broadcast.
- **Send result:** `selected_count >= 1`; `queued_count + not_queued_count = selected_count`. Status is `queued` if all were admitted, `partial` if some were, or `not_queued` if none were. **Queue admission is not recipient receipt.** Continue with other recipients after one fails; the shared layer closes a recipient whose queue is full. Later write failures are logged; no delivery receipts or automatic retries exist in the baseline.
- **Correlation:** chat events use `request_id=null`; send results/request errors echo the request ID. Uncorrelatable connection errors use null. A recipient may receive its event before the sender receives its result.

| Error category | Owner / behavior |
| --- | --- |
| `NO_RECIPIENTS`, `USER_NOT_FOUND`, `SELF_TARGET` | Feature handler; keep the sender connected and publish no chat event |
| `NOT_REGISTERED`, `ALREADY_REGISTERED`, `INVALID_USERNAME`, `USERNAME_TAKEN` | Shared validation; correct the operation or retry registration as appropriate |
| `BAD_REQUEST`, `UNKNOWN_TYPE`, `WRONG_DIRECTION` | Shared layer rejects the request; retain an otherwise usable connection |
| `FEATURE_NOT_IMPLEMENTED`, `FEATURE_DISABLED` | Shared layer distinguishes missing implementation from disabled implementation |
| Frame/JSON/envelope damage, version/ID errors, registration expiry, `INTERNAL_ERROR` | Shared layer; close on `fatal=true`. Error replies are best effort; a broken connection may yield only EOF |

Validation order: frame/JSON → envelope/version/ID → direction/type → fields → registration state → implementation/enabled state → handler. Branch on `code` and `fatal`, not human-readable message text.

## 5. Integration stages and acceptance

**The current delivered stage is F2 plus F3 A in the existing framework.** F2 advertises `{implemented:true, enabled:<startup setting>, variant:null}`; F3 advertises `{implemented:true, enabled:<startup setting>, variant:"A"}`. F1 remains unimplemented and returns `FEATURE_NOT_IMPLEMENTED`. Disabled F2/F3 return `FEATURE_DISABLED`; enabled `/enhance` explains `STARTUP_CONFIG_ONLY`. `build_handlers(config.features)` is the CLI binding; hello, registration and server metadata derive their capability snapshot from those descriptors.

F2 performs exact directory lookup and returns one captured session. Shared publication and actual socket/CLI tests are included. F1 remains an independent handler task. No wire/schema change or standalone protocol adapter was introduced. The old `origin/archive/f2-standalone` branch remains unfixed reference only, never a supported entry point for this delivery.

| Acceptance level | Required evidence |
| --- | --- |
| Historical skeleton | Real concurrent connections/registration, duplicate names, fragmented/coalesced frames and multibyte text, invalid requests, concurrency/cleanup, logs; explicit unavailable responses, zero chat events and zero successful send results |
| Later F1 | Alice sends; Bob and Carol receive; Alice receives no echo. Explicit no-recipient error; disconnected/slow recipients do not stall healthy connections |
| Current F2 | Alice → Bob reaches only Bob; Carol sees no private event. Missing/self targets, malformed input, and same-name reconnection follow the contract |
| Course evidence | Separate localhost and real-device results for both F1 and F2. F3 A localhost implementation/measurements are in its linked acceptance record; skeleton tests cannot substitute for them |

**Future feature developers should return:** existing language/interface compatibility, adapter needs or deviations, owned functions/files, actual validation environment/results, and untested cases. Coordinate any shared message, field, or function-contract change with the foundation owner and coordinator before changing it. Do not independently modify registration or delivery semantics. This brief does not expand baseline v0.2.
