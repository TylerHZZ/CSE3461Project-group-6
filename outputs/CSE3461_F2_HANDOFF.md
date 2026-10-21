# CSE3461 F2 Integration Handoff

> **Subsequent authorization, 2026-10-21:** the user requested a local commit using the supplied English message and a direct push to `origin/main`. Statements below about unstaged/uncommitted work record the initial handoff snapshot. Use Git history and the current remote state for the resulting commit/push status.

2026-10-21 | Feature 2 implementation ready for coordinator independent acceptance

The supported package now sends complete private messages only to the selected registered session, using the existing protocol and thread/queue architecture. Shared publication, message IDs, queue results, capability flags and CLI binding are included. F1/F3 remain unimplemented. This is a scoped F2 delivery, not completion of the course project.

## Repository and changed files

Final repository: `/Users/nira_def/Documents/GitHub/CSE3461Project-group-6`.
Baseline: `main` and local `origin/main` at `8881b8064e6e11005a5a2a9e7a70b5dedd3b161a`.
Reference only: local `origin/one-one` at `1069ff5a35e4eca1b34ec9d59f63fdaf487ac3fe`.

Implementation was prepared from a clean export of that final baseline. The older project workspace was not used as the code source. Final import only replaces reviewed changed files after rechecking original file hashes and repository state; the [integration receipt](f2_work/repository-integration.md) lists the resulting status. Final verification from this repository passed 65/65 tests and a fresh 32-check CLI smoke; its source hashes match the reviewed version. Changes remain unstaged and uncommitted. No stage, commit, push, remote merge or course upload is performed by this workflow.

| Files | Change |
| --- | --- |
| `cse3461_chat/features/private_chat.py` | Exact lookup, self/missing errors, captured one-recipient plan |
| `cse3461_chat/dispatch.py` | Shared ID/event construction, route guard, per-session queue admission, queue-full close, result accounting and correlated response |
| `cse3461_chat/features/__init__.py`, `config.py` | Explicit F2 binding and `--features f2`; default none retained |
| `cse3461_chat/protocol.py`, `server.py`, `telemetry.py` | Descriptor-derived hello/registered/server metadata; wire schema unchanged |
| `tests/test_private.py`, `test_private_faults.py`, `test_publisher.py` | Real sockets, actual CLI, route and fault regressions |
| `tests/test_features.py`, `test_config.py`, `test_skeleton.py` | Update only obsolete F2-unavailable expectations; keep F1/F3 and all earlier safeguards |
| `tests/run_private_smoke.py`, `check_private_mutations.py` | Reproducible CLI evidence and fault-detection check |
| `README.md`, integration/handoff/acceptance docs, `outputs/f2_work`, `outputs/runs/f2-local-20261021-01` | Current instructions, traceable results, historical-status annotations |

`transport.py`, `sessions.py`, client behavior, command grammar and F1/F3 handlers were reused without production changes. No second registry, socket or I/O thread was added. The shared publisher retains future broadcast-plan support as already specified; this does not enable or implement the F1 handler.

## Run and verify

Use a clean checkout containing this change, Python 3.12+ and four terminal windows. No package installation:

```sh
python3 -m cse3461_chat.server --features f2
python3 -m cse3461_chat.client --username alice
python3 -m cse3461_chat.client --username bob
python3 -m cse3461_chat.client --username carol
```

After registration, send `@bob Hello` from Alice and `@alice 中文回复` from Bob. Confirm Carol sees nothing and neither sender receives an own chat echo. Test `@missing Hello`, self-target and `@broken`. Stop with `/quit` or server Ctrl-C. Default `--features none` gives `FEATURE_DISABLED` for F2; F1/F3 still give `FEATURE_NOT_IMPLEMENTED`.

```sh
python3 -m unittest discover -s tests -t . -v
python3 -m tests.run_private_smoke --output outputs/runs/a-new-directory
python3 -m tests.check_private_mutations
```

[Acceptance record](CSE3461_F2_ACCEPTANCE.md): 65 tests passed, 32 actual CLI smoke checks passed, both deliberate defect mutations detected. Full logs and exact environment/source hashes are linked there. Final repository verification and review status are separate evidence, not inferred from implementation claims.

## Standalone branch status

The old bare-string `origin/one-one` implementation is incompatible with the framework. It remains **unmodified and defective historical reference**. Do not use its root `server.py`/`client.py` as the corrected product and do not mechanically merge that branch into this framed implementation. No legacy endpoint is copied here; run `python3 -m cse3461_chat.server` / `.client` as above. The two demonstrated failure classes are fixed in this integrated product by reusing framing and are protected by executable regressions.

## Remaining human actions and limits

1. Coordinator independently review the final working tree, rerun checks and accept or return findings. Inspect/stage/commit the intended files; no commit has been made automatically.
2. Perform actual real-device over-the-air F2 checks: use the server's reachable LAN IPv4 address, connect Alice/Bob/Carol from the agreed devices, repeat bidirectional/isolation/errors/reconnect, save separate new logs and record device/OS/Python/network roles. Several terminals on one Mac do not meet this requirement. Coordinate firewall/network permissions and devices with the team.
3. Align Python versions and verify any other OS. Only Python 3.14.5/macOS was exercised here; Python 3.12 is the supported target, not a tested claim.
4. Complete separately authorized F1/F3 and the course report, Teams video with all members, actual contribution statements, properly named code package/sharing, Carmen submission and personal peer evaluations. No such artifacts or submissions are claimed here.

There are no recipient receipts, authentication, encryption, history, automatic reconnect/retry or heartbeat. Queue admission may be followed by loss if the recipient disconnects or a write fails. Per-sender order is maintained without a global order between senders. F2 has no offline replay. The publisher uses an existing bounded FIFO, so chat can delay later control traffic on that same connection.

## Suggested English commit text

Summary:

```text
Integrate framed private messaging with the shared chat framework
```

Description:

```text
Implement F2 recipient selection and shared queued publication using captured
session IDs, correlated send results, and descriptor-based capabilities.
Enable private messaging with --features f2 while retaining disabled-by-default
behavior and unimplemented F1/F3 handlers.

Replace the standalone one-one runtime path with the existing framed protocol
for the integrated product, preventing long-body truncation and TCP-fragment
misinterpretation. Keep the incompatible standalone branch as historical
reference only.

Add regressions for framing, UTF-8 limits, privacy, reconnect identity,
concurrent ordering, queue saturation, write failure, and actual CLI operation.
Record 65 passing tests, a 32-check localhost CLI run, and two detected defect
mutations. Document remaining real-device and course-delivery work.
```
