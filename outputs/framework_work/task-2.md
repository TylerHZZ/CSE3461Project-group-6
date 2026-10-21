### T2. Implement bounded framed TCP transport

**Files:** Create `cse3461_chat/transport.py`, `tests/test_transport.py`.

**Interfaces:** Consumes T1 decoding/types. Produces `encode_frame(message: WireMessage) -> bytes`, `FramedConnection.receive(deadline_ns: int | None) -> Envelope | None`, `write(message: WireMessage) -> None`, and `close() -> None`. Receive raises transport/protocol failures or `ReadDeadline`. Add foundation-only read metadata for the most recently completed frame: payload byte count and monotonic receive-complete timestamp, captured before decoding/log I/O; it is not a wire field.

- [ ] Write `test_fragmented_multibyte_frame` and `test_coalesced_frames`: split all header boundaries and a UTF-8 code point; concatenate multiple frames; assert exactly the intended ordered envelopes and no lost/duplicated bytes.
- [ ] Write `test_idle_and_partial_deadlines` and `test_eof_boundaries`: idle socket polling is harmless; partial frames expire after 5 seconds from their first byte; caller deadlines also fire while idle; clean between-frame EOF returns `None`, while partial header/body EOF raises `TRUNCATED_FRAME`.
- [ ] Write `test_length_and_failed_write`: lengths 0 and 65,537 are rejected before body allocation; an in-range frame can be decoded; write failure/timeout is surfaced once with no retry; close is idempotent and unblocks reads.
- [ ] Run `python3 -m unittest tests.test_transport -v`; confirm the missing behavior fails.
- [ ] Implement complete-frame encoding, bounded buffered reads that survive timeout polls, one write attempt per frame, and socket shutdown. Preserve the fixed socket timeout and use the earlier applicable receive deadline.
- [ ] Run `python3 -m unittest tests.test_protocol tests.test_transport -v`; require all cases to pass and record the checkpoint.

**Exit evidence:** Actual local socket tests prove framing and failure semantics. They do not prove application registration or chat.

