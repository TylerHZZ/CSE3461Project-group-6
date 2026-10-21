### T6. Implement the terminal client and responsive lifecycle

**Files:** Create `cse3461_chat/commands.py`, `cse3461_chat/client.py`, `tests/test_commands.py`, `tests/test_client.py`; extend `tests/support.py` only for deterministic peer/input fixtures.

**Interfaces:** Consumes T1–T3 and the T5 server contract. Produces `parse_input(line: str) -> ClientCommand | LocalUsageError`; `ClientRuntime.connect(config: ClientConfig, events: EventSink) -> ConnectionInfo`; `send(type: str, data: object) -> int`; `next_event(timeout_s: float) -> ClientEvent | None`; and `close(reason: str) -> None`. The controller alone calls these runtime methods and owns state/pending changes; the receiver posts validated events and transport termination.

- [ ] Write `test_command_grammar`: plain text and `/all <text>` select broadcast; `@bob <text>` selects private; remove the first separating whitespace and preserve the remaining body. `/all @literal` broadcasts literal text. Malformed `@`, missing bodies and unknown slash commands send nothing; `/help` is local; `/enhance` is the empty stub request.
- [ ] Write `test_client_handshake_and_request_state`: show actual local/server endpoints; do not treat TCP connection as registration; allocate increasing request IDs; retry a rejected username; enforce the 5-second hello deadline and 32-pending cap; preserve registered state after feature rejection.
- [ ] Write `test_timeout_and_late_response`: a 10-second request expiry becomes unknown with no resend; registration-reply expiry closes; other late replies show their ID without reopening completed pending state. Invalid server messages close locally without sending a server-style error back.
- [ ] Write `test_terminal_failure_survives_full_event_queue` and `test_untrusted_display_is_escaped`: a full 64-event queue cannot hide EOF/overflow; pending outcomes become unknown. Render unsafe control sequences as safe visible text, including untrusted error details.
- [ ] Run `python3 -m unittest tests.test_commands tests.test_client -v`; confirm the missing behavior fails.
- [ ] Implement command parsing/rendering and the controller state machine. Use a daemon stdin reader with a bounded 16-command queue and no socket/log ownership; block input admission instead of silently dropping commands. Use a non-daemon receiver plus a separate terminal-reason latch so queue overflow is observable. Main/controller is the sole socket writer and terminal output owner.
- [ ] Implement quit/EOF/close with bounded network-worker cleanup, correct exit codes and visible pending outcomes. Local submission is never labeled delivery. Do not implement automatic reconnect or resend.
- [ ] Run `python3 -m unittest tests.test_commands tests.test_client -v`; require all cases to pass and record the checkpoint.

**Exit evidence:** The actual terminal client participates in the framework lifecycle while still reporting all three features unavailable.

