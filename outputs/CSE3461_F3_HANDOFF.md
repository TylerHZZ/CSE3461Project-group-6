# CSE3461 Feature 3 A Handoff

> Coordinator update, 2026-10-21: F2/F3 passed independent localhost acceptance and are integrated into main by the commit containing this update. See [fresh acceptance and evidence](CSE3461_COORDINATOR_ACCEPTANCE.md). Earlier implementation-stage Git states and pending-review statements below describe historical delivery snapshots, not current repository status.

2026-10-21 | Implementer delivery; coordinator independent acceptance remains separate.

## Repository, branch and scope

Final repository: `/Users/nira_def/Documents/GitHub/CSE3461Project-group-6`.
Baseline HEAD: `64a0459bbb2a79745574be629093b82d83dcf7ae`.
Working branch: `feature/f3-delay-jitter`, tracking `origin/feature/f3-delay-jitter`.

At the user's explicit additional request, the branch was created on GitHub **before implementation**, pointing to the already-existing baseline commit. This was the only push. Product changes remain local, unstaged and uncommitted on that branch; no implementation commit, main update, PR, merge or course submission is performed. The old `3541 Project 1` development copy was not copied over the final repository. Initial plan/baseline preparation was exported from the final baseline; after branch creation all implementation and experimental verification ran in the final checkout.

F3 A adds fixed delay or uniform jitter immediately before server-to-recipient chat writes, using the already-working F2 publication chain. F1 remains unimplemented. No additional transport, wire message, encryption, GUI, persistence, dependency or plugin engine is introduced.

## Files and interfaces

| Location | Change |
| --- | --- |
| `features/enhancement.py` | Writer-owned `DelayPolicy`, `WaitObservation`, startup-only enhancement command explanation |
| `config.py`, `features/__init__.py`, `server.py`, `commands.py` | Validated options, F3 implemented/enablement/variant A, startup metadata and help |
| `sessions.py` | Optional `delay_config` on SessionManager; per-session cancel event/policy; chat-only hook, enqueue/dequeue/wait/write timing, in-flight discard accounting |
| `client.py` | Body-free `chat_received` event after validation using receiver-thread completion timestamp |
| `experiments/sender.py`, `run_delay.py`, `analyze_delay.py` | Production-client workload driver, actual process orchestration, strict local-clock analysis and CSV export |
| `tests/test_delay*.py`, `test_client.py`, existing fixture/capability/smoke tests | New F3 coverage and only superseded F3-unavailable expectations updated; original F2 tests preserved |
| README, current integration/handoff documents, F3 documents and evidence directories | Configuration, status, data, limitations and reproduction |

`DelayPolicy.before_chat_write(cancel)` selects one value from its writer-owned RNG, measures the actual Event.wait interval and reports cancellation. `SessionManager` waits without holding directory or telemetry locks. Per-recipient FIFO remains; no global sender order is added. The existing 64-frame queue and publication counters remain unchanged. `send_result` is still queue admission, never delivery.

Closing a session signals cancellation. Under F3, interrupted in-flight and remaining queued chat are discarded/countable; existing controls and shutdown bye may drain. Control frames receive no direct wait but can queue behind chat. F3 off retains original drain behavior. A disconnect can still race a completed wait/socket write, so no delivery guarantee is added.

## Run and reproduce

From the final repository with Python 3.12+ (actually verified on Python 3.14.5/macOS):

```sh
python3 -m cse3461_chat.server --features f2,f3 --delay-mode fixed --delay-ms 20
python3 -m cse3461_chat.client --username alice
python3 -m cse3461_chat.client --username bob
python3 -m cse3461_chat.client --username observer
```

Use separate terminals. Send `@bob hello` from Alice; Bob receives, observer stays silent. For jitter replace fixed options with `--delay-mode jitter --delay-ms 20 --jitter-ms 15 --delay-seed 20261021`. `/enhance` cannot mutate policy: F3 disabled returns FEATURE_DISABLED, enabled returns nonfatal STARTUP_CONFIG_ONLY. Both hello and registered advertise actual F3 implemented/enabled state and variant A.

```sh
python3 -m unittest discover -s tests -t . -v
python3 -m tests.run_private_smoke --output outputs/runs/another-f2-check
python3 -m tests.check_private_mutations
python3 -m experiments.run_delay --output outputs/runs/another-f3-experiment
python3 -m experiments.analyze_delay --input outputs/runs/another-f3-experiment
```

Output directories must be new. Loopback bind/connect permission is required. The mutation checker intentionally prints failures for mutated implementations and returns success only when both known defects are caught. Read [acceptance](CSE3461_F3_ACCEPTANCE.md) and [analysis](CSE3461_F3_ANALYSIS.md) for final evidence, exact metric definitions and results.

Policy bounds: finite values with `0 <= jitter <= delay`, `delay+jitter <= 1000` ms; fixed requires jitter 0; off requires delay/jitter 0. Seed integer 0..4294967295. `f3` and fixed/jitter must be enabled together. `f3` alone is supported but produces no chat without an enabled producer such as F2. Enabled fixed 0 is a tested no-sleep control. Jitter is uniform on [delay-jitter,delay+jitter], seeded independently from SHA-256 of `seed:username`. Reconnect restarts that username's sequence. Seeded selection is reproducible for the same runtime and recipient sequence; OS timing is not.

## Coordinator independent acceptance

1. Verify working branch/upstream, baseline HEAD and unstaged diff; review production code plus untracked experiment/tests. Do not use the old workspace copy.
2. Run full suite and a fresh F2 smoke. Inspect F1 unavailable and F3 default-disabled/variant-A capabilities.
3. Run a fresh nine-condition experiment and analyze it. Inspect all five logs per run, exit codes, manifest source hashes, strict admission/dequeue/wait/write/receipt joins, counts, selected vs actual delays and both recipients' FIFO.
4. Stop a delayed server while chat is queued and confirm interruption/bye behavior; tests include full queue, disconnected recipient, concurrent recipient and telemetry-failure cases.
5. Review actual AI contribution and remaining human coursework. Commit or push implementation only on later explicit user authorization, and never merge to main automatically.

Rollback the active experiment with `--features f2` and default off/zero delay options. To remove code, review this task's tracked diff and new-file inventory and reverse only those changes after preserving later work. No blanket reset/clean is prescribed.

## Actual AI assistance and remaining human work

OpenAI Codex assisted with reading the existing architecture/assignment, refining configuration/randomness/measurement design, writing implementation and regression tests, operating real localhost experiments, validating calculations, correcting the analysis acceptance gap found by an independent code-review agent, and drafting this handoff. The measurements were produced by real server/client processes, not generated as illustrative numbers. This statement does not assign AI work to any student or invent individual team contributions. Students must review, understand and adapt the work and truthfully report their own contributions and AI use under course policy.

No physical-device run, Wi-Fi propagation measurement, authenticated/encrypted deployment, student live demonstration, final course PDF, video, named Carmen-group archive, sharing or submission is claimed. F1 remains unfinished. Python 3.12 is the supported floor, but only Python 3.14.5/macOS was exercised here. The source archive is a local review convenience; confirm the actual group name before any course submission.

## Suggested English commit text

Summary:

```text
Add controlled chat delay and jitter with reproducible F3 experiments
```

Description:

```text
Implement F3 A as a configurable, seeded per-recipient delay policy in the
existing TCP writer path. Preserve FIFO, private-message isolation, bounded
queues and admission-only send results. Interrupt waits on connection close
and record actual wait, queue, write and recipient-receipt evidence.

Add strict configuration and capability reporting, regression coverage for
zero/disabled behavior, jitter, cancellation, saturation and telemetry failure,
and a real-process localhost experiment runner with failure-inclusive analysis.
Retain F1 as unimplemented and document actual AI assistance, reproducible
commands, raw measurements and remaining course/device work.
```
