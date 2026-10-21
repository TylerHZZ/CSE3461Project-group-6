### T5. Wire the server and unavailable feature paths

**Files:** Create `cse3461_chat/dispatch.py`, `cse3461_chat/server.py`, `cse3461_chat/features/__init__.py`, `cse3461_chat/features/broadcast.py`, `cse3461_chat/features/private_chat.py`, `cse3461_chat/features/enhancement.py`, `tests/test_dispatch.py`, `tests/test_features.py`, and initial `tests/test_skeleton.py`.

**Interfaces:** Consumes T1–T4. Produces `Dispatcher.handle(session_id: str, envelope: Envelope, received_ns: int) -> None`; the frozen publisher/handler interfaces in §2; `handle_enhancement(ctx: RequestContext, request: EmptyEnhancementRequest) -> AppError`; `build_handlers() -> HandlerTable`; `ServerRuntime.run(config: ServerConfig, handlers: HandlerTable, events: EventSink) -> int`; and `ServerRuntime.stop(reason: str) -> None`.

- [ ] Write table-driven `test_dispatch_validation_order`: version/ID → direction/type → body → state → implementation/enabled gate. Include unknown type, wrong direction, pre-registration feature request, duplicate registration, and best-effort fatal errors with correct correlation.
- [ ] Write `test_rejected_body_consumes_id` and `test_spoofed_sender_never_dispatches`: a body rejection consumes the valid ID; reuse then causes fatal `BAD_REQUEST_ID` with null correlation. Extra `sender` is rejected, and a handler spy records zero invocations.
- [ ] Write `test_feature_stubs_and_publisher_are_unavailable`: direct calls and valid wire requests return `FEATURE_NOT_IMPLEMENTED` with the correct `f1/f2/f3`. A fixture route plan still cannot make the publisher emit chat or return a send result. Verify the separate disabled gate with a descriptor-only test fixture, without activating any runtime feature.
- [ ] Write `test_three_clients_with_one_unregistered`, `test_capacity_rejection_before_workers`, and `test_listener_failures`: one idle registration does not block two others; the seventeenth connection is closed before session workers start at the default capacity; bind failure produces no false listening state.
- [ ] Run `python3 -m unittest tests.test_dispatch tests.test_features tests.test_skeleton -v`; confirm the missing behavior fails.
- [ ] Implement dispatcher, unavailable stubs, explicit handler wiring, and the server entry point. Queue hello first; enforce the acceptance-time registration deadline and monotonic request IDs; start one receiver/writer pair per admitted connection; contain client failures without stopping healthy sessions.
- [ ] Implement bounded server supervision: stop accepting, initiate all session closes, then join against one overall 5-second deadline. Do not spend a fresh 2-second drain or 5-second join budget sequentially on every session. Signal handling requests stop without blocking on network operations.
- [ ] Run `python3 -m unittest tests.test_dispatch tests.test_features tests.test_skeleton -v`; require all cases to pass and record the checkpoint.

**Exit evidence:** A real server accepts and registers raw framed clients, handles control traffic, and rejects every feature honestly. No terminal-client completion claim yet.

