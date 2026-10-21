### T3. Establish configuration and evidence recording

**Files:** Create `cse3461_chat/config.py`, `cse3461_chat/telemetry.py`, `tests/test_config.py`, `tests/test_telemetry.py`.

**Interfaces:** Consumes T1 constants/schema rules. Produces immutable `ServerConfig`/`ClientConfig`; `parse_server_args(argv: Sequence[str] | None) -> ServerConfig`; `parse_client_args(argv: Sequence[str] | None) -> ClientConfig`; `open_event_sink(role: Literal["server", "client"], run_id: str | None, log_file: str | None) -> EventSink`; `EventSink.emit(name: str, fields: object) -> None`; `EventSink.close() -> None`; and a visible `TelemetryError` failure. An omitted log path creates no log file; an omitted run ID is generated per actual process run and is not assumed shared across clients.

- [ ] Write `test_config_defaults_and_rejections`: assert the values in §3, validate addresses/ports/usernames, reject nonpositive capacity and any requested unimplemented feature, and preserve argument-error exit 2.
- [ ] Write `test_jsonl_sequence_and_metadata`: concurrent emits produce complete parseable records with unique increasing local `seq`, schema version 1, process-instance UUID, run ID, role, UTC time, monotonic time, event, and fields. Preserve event-specific occurrence timestamps rather than substituting later log-write time.
- [ ] Write `test_log_open_failure_precedes_network` and `test_runtime_log_failure_is_visible`: opening a requested inaccessible destination fails; a controlled later write failure raises `TelemetryError`. Verify no message-body field is added by the sink. Runtime shutdown effects are exercised in T7.
- [ ] Run `python3 -m unittest tests.test_config tests.test_telemetry -v`; confirm the missing behavior fails.
- [ ] Implement configuration validation and the small serialized JSONL sink. Open requested logs before network startup; let runtimes contain failures and report invalid evidence. Keep log I/O outside session locks.
- [ ] Run `python3 -m unittest tests.test_config tests.test_telemetry -v`; require all cases to pass and record the checkpoint.

**Exit evidence:** Validated startup configuration and inspectable evidence records. No experiment metrics, result CSVs, or prefilled success records exist.

