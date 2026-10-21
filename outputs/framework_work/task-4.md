### T4. Implement session registration, queues, and cleanup

**Files:** Create `cse3461_chat/sessions.py`, `tests/test_sessions.py`; add only needed shared fixtures to `tests/support.py`.

**Interfaces:** Consumes T1 types, T2 channels, T3 limits/event sink. Produces immutable `SessionView`, read-only `Directory.find(username: str) -> SessionView | None`, `Directory.others(origin_session_id: str) -> tuple[SessionView, ...]`, and these `SessionManager` methods: `register(session_id, username, registered_reply) -> SessionView | AppError`; `enqueue(session_id, message, meta: DeliveryMeta | None) -> EnqueueResult`; `close(session_id, reason, final_message: WireMessage | None, drain: bool) -> None`. Runtime-only helpers own attachment, state/ID access, and worker/queue coordination; callers never mutate maps directly.

- [ ] Write `test_atomic_registration_and_deadline`: simultaneous claims for one username have exactly one winner; an invalid/duplicate name can retry only within the original 30 seconds; unregistered connections consume capacity; failed registration-reply admission creates no active name.
- [ ] Write `test_registered_reply_precedes_visibility` and `test_directory_snapshots`: `registered` is queued before lookup exposes the session; directory snapshots include only registered, non-closing sessions and expose no socket.
- [ ] Write `test_stale_cleanup_preserves_replacement`: disconnect and reuse a username, then repeat old-session cleanup; the new session survives. Enqueue to the old ID returns closed and never targets the replacement.
- [ ] Write `test_full_queue_isolates_connection` and `test_concurrent_control_frames`: fill the 64-frame queue without a writer; the next admission reports `full`; closing that session preserves another healthy session. Concurrent producers through one writer yield complete control frames without interleaving bytes or losing admitted records.
- [ ] Run `python3 -m unittest tests.test_sessions -v`; confirm the missing behavior fails.
- [ ] Implement manager-owned connection state, one short registry lock, bounded FIFO admission, and idempotent closing. Use an already-locked enqueue helper for registration; record events and perform socket operations only after releasing the registry lock. Remove the active username before draining, avoid self-join, and retain connection capacity until cleanup completes.
- [ ] Run `python3 -m unittest tests.test_sessions -v`; require all cases to pass and record the checkpoint. Use barriers/events for race tests rather than relying on arbitrary sleeps.

**Exit evidence:** Real registration and lifecycle infrastructure with tested invariants. No feature handler selects recipients or publishes chat.

