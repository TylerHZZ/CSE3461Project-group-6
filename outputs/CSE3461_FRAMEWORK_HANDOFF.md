# CSE3461 Framework Handoff — Current F2 Integration

2026-10-21 | Protocol v1 / architecture contract v0.2 retained

The framework now supports **F2 private messages** through its existing length-prefixed TCP connection, directory and bounded queues. The shared publisher creates message IDs and chat events, records routing/admission metadata, handles unavailable/full recipients and returns queue counts. The dispatcher sends correlated `send_result` replies. F1 broadcast and F3 A are still unimplemented.

Use Python 3.12+ with no dependencies, in separate terminals:

```sh
python3 -m cse3461_chat.server --features f2
python3 -m cse3461_chat.client --username alice
python3 -m cse3461_chat.client --username bob
python3 -m cse3461_chat.client --username carol
```

Alice enters `@bob Hello Bob`; Bob alone sees it. Default `--features none` disables F2 and returns `FEATURE_DISABLED`. Unknown/self targets return `USER_NOT_FOUND` / `SELF_TARGET`. Invalid private input never becomes a broadcast.

The F2 implementation and its limits are documented in [F2 handoff](CSE3461_F2_HANDOFF.md). [F2 acceptance](CSE3461_F2_ACCEPTANCE.md) links the full suite, mutation checks, real CLI demonstration and requirement mapping. [README](../README.md) provides a clean-environment walkthrough and the [integration brief](CSE3461_F1_F2_INTEGRATION_BRIEF.md) preserves all shared interfaces.

## Integration surfaces

- `features.private_chat.handle_private(ctx, request) -> RoutePlan | AppError`: exact read-only lookup and one captured session.
- `features.broadcast.handle_broadcast` and `features.enhancement.handle_enhancement`: unchanged stubs.
- `dispatch.Publisher(manager).publish(ctx, request, plan) -> PublishResult | AppError`: shared publication for private and future broadcast plans; no new routing handler or socket thread.
- `features.build_handlers(features='none')`: immutable implementation/enablement bindings. CLI passes the validated startup choice.
- `protocol.capabilities(descriptors=None)`: actual server descriptors when supplied; an unknown/all-unavailable initial state for clients before hello when omitted.
- `SessionManager`, `Directory.find`, `Directory.others`, `FramedConnection` and wire field definitions: unchanged.

Only the connection writer sends frames. Recipient identity is captured by session ID, not re-resolved by name during publication. A queue-full recipient closes independently of healthy recipients. Queue admission does not promise a later write or receipt. Per-sender FIFO is preserved; no global order is promised.

## Earlier framework history

The original skeleton was committed as `8881b8064e6e11005a5a2a9e7a70b5dedd3b161a`. Its [49-test acceptance](CSE3461_FRAMEWORK_ACCEPTANCE.md), [review/fixes](framework_work/final-review.md), [repository import](framework_work/repository-import.md), and [supervised run](runs/skeleton-smoke-20261021-01/smoke-summary.json) are retained as historical evidence. Statements in those records that F2/publication are unavailable describe that earlier stage.

This integration derives from that actual repository commit; it does not overwrite the repository with the older project copy. The separate `origin/one-one` raw-string branch remains unfixed historical reference and is not the recommended runtime. Its incompatible protocol was not merged.

Real-device over-the-air verification, other OS/Python-version checks, F1/F3, team contributions, video, report, sharing and course submission remain separate. No external communication, push or course upload is part of this delivery. The coordinator retains independent acceptance responsibility.
