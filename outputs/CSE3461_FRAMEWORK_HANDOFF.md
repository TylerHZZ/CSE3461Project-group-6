# CSE3461 Framework Handoff — Current F1/F2/F3 Integration

2026-10-21 | Protocol v1 / architecture contract v0.2 retained

The framework now supports **F1 broadcasts and F2 private messages** through its existing length-prefixed TCP connection, directory and bounded queues. The shared publisher creates message IDs and chat events, records routing/admission metadata, handles unavailable/full recipients and returns queue counts. The dispatcher sends correlated `send_result` replies. F3 A controlled delay/jitter applies to both message modes. F1 originates in teammate commit `ee35fe6`, retained in the feature branch history; see [F1 handoff](CSE3461_F1_HANDOFF.md). See [F3 handoff](CSE3461_F3_HANDOFF.md) for configuration, measured evidence and closure semantics.

Use Python 3.12+ with no dependencies, in separate terminals:

```sh
python3 -m cse3461_chat.server --features f2
python3 -m cse3461_chat.client --username alice
python3 -m cse3461_chat.client --username bob
python3 -m cse3461_chat.client --username carol
```

Alice enters `@bob Hello Bob`; Bob alone sees it. Use `--features f1,f2` to also enable plain text or `/all` broadcasts to every other registered session. Default `--features none` disables all implemented features and returns `FEATURE_DISABLED`. Unknown/self targets return `USER_NOT_FOUND` / `SELF_TARGET`. Invalid private input never becomes a broadcast.

The F2 implementation and its limits are documented in [F2 handoff](CSE3461_F2_HANDOFF.md). [F2 acceptance](CSE3461_F2_ACCEPTANCE.md) links the full suite, mutation checks, real CLI demonstration and requirement mapping. [README](../README.md) provides a clean-environment walkthrough and the [integration brief](CSE3461_F1_F2_INTEGRATION_BRIEF.md) preserves all shared interfaces.

## Integration surfaces

- `features.private_chat.handle_private(ctx, request) -> RoutePlan | AppError`: exact read-only lookup and one captured session.
- `features.broadcast.handle_broadcast(ctx, request) -> RoutePlan | AppError`: original teammate handler, returning `directory.others(sender.session_id)` snapshot or `NO_RECIPIENTS`. F3 is a writer policy; `handle_enhancement` explains startup-only operation when enabled.
- `dispatch.Publisher(manager).publish(ctx, request, plan) -> PublishResult | AppError`: shared publication for private and broadcast plans; no new routing handler or socket thread.
- `features.build_handlers(features='none')`: immutable implementation/enablement bindings. CLI passes the validated startup choice.
- `protocol.capabilities(descriptors=None)`: actual server descriptors when supplied; an unknown/all-unavailable initial state for clients before hello when omitted.
- `SessionManager` gains optional delay configuration, per-session cancellation and timing events. Directory and wire contracts remain unchanged.

Only the connection writer sends frames. Recipient identity is captured by session ID, not re-resolved by name during publication. A queue-full recipient closes independently of healthy recipients. Queue admission does not promise a later write or receipt. Per-sender FIFO is preserved; no global order is promised.

## Earlier framework history

The original skeleton was committed as `8881b8064e6e11005a5a2a9e7a70b5dedd3b161a`. Its [49-test acceptance](CSE3461_FRAMEWORK_ACCEPTANCE.md), [review/fixes](framework_work/final-review.md), [repository import](framework_work/repository-import.md), and [supervised run](runs/skeleton-smoke-20261021-01/smoke-summary.json) are retained as historical evidence. Statements in those records that F2/publication are unavailable describe that earlier stage.

This integration derives from that actual repository commit; it does not overwrite the repository with the older project copy. The separate `origin/archive/f2-standalone` raw-string branch remains unfixed historical reference and is not the recommended runtime. Its incompatible protocol was not merged.

F2/F3 passed coordinator independent localhost acceptance and were merged into main and pushed in `5e365fe`; see the [coordinator acceptance record](CSE3461_COORDINATOR_ACCEPTANCE.md). F1 has now passed [independent coordinator acceptance](CSE3461_F1_COORDINATOR_ACCEPTANCE.md) and is integrated into main. The teammate handler and source history are preserved; this workflow adds compatibility wiring, regression tests and evidence. The main branch now includes all three features for the verified localhost scope. Real-device over-the-air verification, other OS/Python-version checks, team contributions, video, report, sharing and course submission remain separate. No course upload or submission is claimed.
