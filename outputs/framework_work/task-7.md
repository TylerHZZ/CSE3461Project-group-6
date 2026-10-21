### T7. Verify the complete framework and prepare the handoff

**Files:** Extend `tests/test_skeleton.py` and existing focused tests only for remaining acceptance gaps; create `README.md`, then the actual acceptance record and run evidence listed in §3.

**Interfaces:** Consumes the completed client/server entry points and every earlier task's interfaces. Produces an acceptance record mapped to S01–S14, reproducible startup instructions, and an explicit list of remaining feature work.

- [ ] Add `test_requested_log_open_failure_starts_no_network`: exercise both entry points with an unusable requested log destination; assert nonzero exit and no listener/connect call. This verifies startup ordering beyond the sink's unit test.
- [ ] Add `test_server_stop_with_blocked_stdin`, `test_multi_session_shutdown_budget`, and `test_runtime_logging_failure_stops_process`: use actual subprocesses/pipes or controlled socket peers; prove shutdown without an extra keystroke, a shared 5-second shutdown target, and nonzero exit plus invalid-evidence diagnostics after a requested log fails.
- [ ] Add `test_logs_omit_message_bodies` and `test_cli_and_raw_features_remain_unavailable`: use distinctive body text, check logs contain no body, exercise all three feature paths, and assert no recipient chat events or sender send results. Use bounded observation plus synchronized request completion, not an unbounded wait for a forbidden event.
- [ ] Run `python3 -m unittest tests.test_skeleton -v`; identify any missing behavior and repair only the owning framework modules. Do not relax the accepted boundary to make tests pass.
- [ ] Write README commands that match the implemented argument parser, shared-type import locations, feature ownership, timeout/outcome language, and links to the baseline/brief. Explain LAN addressing without claiming a physical-device test.
- [ ] Run `python3 -m unittest discover -s tests -t . -v`; require zero failures/errors. Run both `python3 -m cse3461_chat.server --help` and `python3 -m cse3461_chat.client --help` and check the documented arguments.
- [ ] Perform the manual localhost scenario in §5 with one server and three actual clients. Record observed results and failures, interpreter/OS, configuration and actual log paths; create evidence files only from these runs.
- [ ] Review ownership and scope against S13: actual threads, one socket writer, no I/O/logging/waits under registry lock, immutable feature descriptors, no active handlers/publisher, no F3 hook, and no unbounded shutdown loop. Record any unresolved finding rather than declaring acceptance.
- [ ] Complete `outputs/CSE3461_FRAMEWORK_ACCEPTANCE.md`: each S01–S14 row states pass/fail/not run, evidence location, environment, and limitations. Stop after the framework handoff; do not begin P4/P5 automatically.

**Exit evidence:** All S01–S14 are supported by actual checks with no unresolved acceptance failure. If any mandatory row is failed or unrun, report partial completion with that exact gap.

