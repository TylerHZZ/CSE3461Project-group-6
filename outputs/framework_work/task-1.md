### T1. Freeze executable protocol contracts

**Files:** Create `cse3461_chat/__init__.py`, `cse3461_chat/protocol.py`, `tests/__init__.py`, `tests/test_protocol.py`.

**Interfaces:** Consumes baseline §5 and §7. Produces `decode_payload(payload: bytes) -> Envelope | ProtocolError` and `validate_message(envelope: Envelope, direction: Literal["c2s", "s2c"]) -> WireMessage | AppError`, plus the shared types listed in §7. Encoding is T2's responsibility. `WireMessage` and its validated payload must remain immutable.

- [ ] Write `test_strict_envelope_and_json`: duplicate JSON keys, invalid UTF-8, non-finite values, non-object JSON, extra envelope fields, and boolean IDs are rejected with the baseline error class; valid unknown types remain envelopes until typed validation.
- [ ] Write `test_message_schemas_and_direction`: cover every type in baseline §5.3, exact required fields, wrong-direction errors, username boundaries 1/24/25, and text byte boundaries 1/4,096/4,097. Include multibyte text and a forbidden control character. `chat_message`/`send_result` are validated contracts, not enabled behavior.
- [ ] Run `python3 -m unittest tests.test_protocol -v`; confirm the missing behavior fails.
- [ ] Implement the types and two functions with ordered envelope versus payload checks. Preserve unknown type/version for the dispatcher's subsequent ordered validation; do not consume request IDs here.
- [ ] Run `python3 -m unittest tests.test_protocol -v`; require all cases to pass and record the checkpoint.

**Exit evidence:** Validated shared data types and schema behavior, with no sockets, feature routing, or application startup yet.

