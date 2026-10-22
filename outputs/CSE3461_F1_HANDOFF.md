# F1 broadcast integration handoff

2026-10-21 | Implementer delivery for independent coordinator acceptance. Work remains on `feature/f1-broadcast`; no main merge or course submission.

## Repository and provenance

Authoritative repository: `/Users/nira_def/Documents/GitHub/CSE3461Project-group-6`.
Main integration base: `8eee99616500ec9eed92b869a2b5f0544ce78597`.
Teammate source: `ee35fe66e0a621750148309c0bdea262cdaca5ef`, parent `64a0459bbb2a79745574be629093b82d83dcf7ae`, original Git author **Aaditya**. Original branch spelling: `brodcast-feature`.

The feature branch was created from current main, pushed and assigned upstream **before implementation**. The exact original F1 commit is retained as a merge parent, preserving its author and ancestry; `archive/f1-original` additionally points to that exact source. `brodcast-feature` is retained, not deleted or force-pushed. It must be checked again for later teammate work before any old-name cleanup. No F2/F3 branch history was changed. The old ChatGPT workspace was never copied over the real repository.

The source already used the shared framework. Its broadcast handler remains **byte-for-byte identical** to the teammate's code: capture `directory.others(sender.session_id)`, return `RoutePlan` or nonfatal `NO_RECIPIENTS`. Original tests: 69/69; independent additional boundary checks against that isolated original: 6/6. No reproducible original routing defect was found. The source predates F3; its F3-unimplemented configuration is an integration difference, not evidence that its original F1 feature is defective. [Provenance and hashes](f1_work/provenance.json) records this distinction.

## What this integration contributes

- Reconcile F1 startup configuration, handler capabilities and server status with main's F3; allow all eight canonical feature subsets with default `none` and unchanged F3 mode validation.
- Retain teammate handler/basic broadcast tests; update obsolete F1-unimplemented assertions, preserving unavailable-error protocol tests and existing security/lifecycle coverage.
- Add real-socket broadcast framing, concurrency, lookup snapshot, reconnection and queue-isolation tests; add F1/F3 off, zero, fixed, jitter, FIFO, saturation and cancellation checks.
- Add actual CLI broadcast evidence with complete receiver-pair accounting and unchanged F2/F3 reruns. Update current run/interface documentation and this delivery record.

There is no new protocol, registry, socket thread or publisher. `dispatch.py`, `sessions.py`, `protocol.py`, `transport.py`, `client.py`, `commands.py`, the F2/F3 handlers and all three experiment modules remain unchanged from main. Existing publisher IDs/admission counts and writer lifecycle are reused.

| Changed area | Files |
| --- | --- |
| Product wiring | `cse3461_chat/config.py`, `features/__init__.py`, `server.py` |
| Teammate handler preserved | `cse3461_chat/features/broadcast.py` |
| Teammate tests / adapted baseline expectations | `tests/test_broadcast.py`, `test_config.py`, `test_dispatch.py`, `test_features.py`, `test_skeleton.py`, `test_delay.py`, `test_private.py`, `run_private_smoke.py` |
| Additional integration evidence tooling | `tests/test_broadcast_integration.py`, `test_broadcast_delay.py`, `run_broadcast_smoke.py` |
| Current documentation | `README.md`, `REPOSITORY_GUIDE.md`, `outputs/CSE3461_FRAMEWORK_HANDOFF.md`, `CSE3461_F1_F2_INTEGRATION_BRIEF.md`, F1 PLAN/HANDOFF/ACCEPTANCE |
| Raw evidence | `outputs/f1_work/` including original/main baselines, failed developmental checks, successful final checks, process logs and source hashes |

Previous coordinator/F2/F3 acceptance reports remain historical and were not rewritten as new F1 acceptance.

## Run and reproduce

Python 3.12+ standard library; actual environment Python 3.14.5/macOS. In separate terminals:

```sh
python3 -m cse3461_chat.server --features f1,f2
python3 -m cse3461_chat.client --username alice
python3 -m cse3461_chat.client --username bob
python3 -m cse3461_chat.client --username carol
```

After registration, Alice's plain text or `/all hello` reaches Bob and Carol with the same message ID; Alice receives a queue result and no echo. Bob can broadcast back. `@bob secret` reaches only Bob. Malformed `@...` input stays a local usage error; an absent private target stays `USER_NOT_FOUND`, with no broadcast fallback. `/all @literal` explicitly broadcasts leading `@`. With no other registered non-closing session, broadcast returns `NO_RECIPIENTS` and leaves the sender connected.

F3 example: `python3 -m cse3461_chat.server --features f1,f2,f3 --delay-mode jitter --delay-ms 20 --jitter-ms 15 --delay-seed 20261021`. For fixed use `--delay-mode fixed --delay-ms 20` and omit jitter. Each recipient retains its own FIFO, seeded sequence and cancellation. Controls have no injected delay but may queue behind chat.

```sh
python3 -m unittest discover -s tests -t . -v
python3 -m tests.run_broadcast_smoke --output outputs/runs/new-f1-check
python3 -m tests.run_private_smoke --output outputs/runs/new-f2-check
python3 -m tests.check_private_mutations
python3 -m experiments.run_delay --output outputs/runs/new-f3-check
python3 -m experiments.analyze_delay --input outputs/runs/new-f3-check
```

Use new output directories. All network tests require loopback permission. Mutation-check printed failures are deliberate injected faults; exit 0 means both regressions detected them. The F3 runner/analyzer is unchanged and still runs nine private-message trials; the new broadcast runner provides separate F1/F3 integration evidence. Detailed results and the feature matrix are in [acceptance evidence](CSE3461_F1_ACCEPTANCE.md).

## Semantics and limits

Broadcast membership is captured at lookup time. Later joiners and same-name replacement sessions receive no prior traffic. `queued`/`partial`/`not_queued` describe queue admission, never receipt. Counts include all captured recipients even if they close before publication. One unavailable/full recipient does not stop others; a full recipient is closed by the existing shared publisher. Accepted messages can still be lost to disconnect/write failure. Only per-sender order is promised, not a global order across senders.

Only localhost on this Mac/Python was verified. Physical-device/over-the-air F1 and F2, other OS/Python versions, actual student contribution statements, Teams video, final report, sharing and course submission remain unverified/unperformed. No public deployment, authentication, encryption, offline replay or delivery receipt is introduced.

OpenAI Codex performed this integration, test expansion, local execution, evidence checks and documentation with an independent code-review agent. The original F1 implementation remains attributed to its Git author. AI work is not assigned to any student; team members must truthfully report their actual work and AI assistance.

## Coordinator handback

Review the feature branch against the stated main base, verify original source ancestry/handler equality and the fresh source/log hashes, then rerun acceptance as desired. Independent implementation review is recorded separately from coordinator acceptance. Do not merge/push main automatically. Leave `brodcast-feature` until the coordinator/team confirms old-name cleanup after checking its current tip; its archive is a source snapshot, not a defect label. Current Git commit identifiers and final clean/pushed state are recorded in the delivery response and Git history.
