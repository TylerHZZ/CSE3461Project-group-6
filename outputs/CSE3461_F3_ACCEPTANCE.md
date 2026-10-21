# Feature 3 A Acceptance Evidence

> Coordinator update, 2026-10-21: F2/F3 passed independent localhost acceptance and are integrated into main by the commit containing this update. See [fresh acceptance and evidence](CSE3461_COORDINATOR_ACCEPTANCE.md). Earlier implementation-stage Git states and pending-review statements below describe historical delivery snapshots, not current repository status.

2026-10-21 | F3 implementation and localhost verification complete; coordinator independent acceptance pending.

## Result and repository identity

Final repository: `/Users/nira_def/Documents/GitHub/CSE3461Project-group-6`.
Baseline and unchanged HEAD: `64a0459bbb2a79745574be629093b82d83dcf7ae`.
Branch: `feature/f3-delay-jitter`, upstream `origin/feature/f3-delay-jitter`.

**89/89 automated tests pass**, including all 65 baseline tests in substance, with only obsolete F3-unimplemented expectations updated. **32/32 actual F2 CLI smoke checks pass**. Both original truncation and one-recv framing mutations are detected. Final F3 evidence has **nine real process runs, all passing normal acceptance, 540/540 observed target-message pairs, no private events at sender/observer**.

The user required creating the GitHub feature branch before development. That reference was created at the remote's existing baseline; no new code was committed or pushed. All implementation changes are unstaged/uncommitted in that branch's final checkout. Main was not updated. No course upload, PR or merge occurred.

## Reproducible evidence

| Check | Evidence | Actual result |
| --- | --- | --- |
| Original F2 baseline in final repository | [baseline suite](f3_work/baseline-suite.txt) | 65 tests, 8.090 s, pass |
| Initial sandbox-only attempt | [denied run](f3_work/baseline-sandbox-denied.txt) | Loopback permission denied; not treated as product failure or passing evidence |
| Policy/config before implementation | [red](f3_work/policy-red.txt) / [green](f3_work/policy-green.txt) | 4 missing-feature failures, then pass |
| Writer integration before implementation | [red](f3_work/writer-red.txt) | 8 missing-hook failures |
| Explicit recipient evidence | [red](f3_work/receipt-red.txt) / [green full suite](f3_work/receipt-green-suite.txt) | Missing chat_received assertion exposed; 78-test stage passed after implementation |
| Analyzer arithmetic/failure fixtures | [initial red](f3_work/analysis-red.txt) / [green](f3_work/analysis-green.txt) | Real denominator, elapsed-wait, missing-log and local-clock checks |
| Independent-review repairs | [missing-stage red](f3_work/review-analysis-red.txt), [green](f3_work/review-analysis-green.txt), [identity red](f3_work/review-identity-red.txt), [green](f3_work/review-identity-green.txt) | Missing/contradictory measurement and identity chains now rejected; 10 analyzer tests pass |
| Final complete suite in final repository | [final suite](f3_work/final-suite.txt) | 89 tests, 10.557 s, pass |
| Actual F2 regression CLI processes | [32-check summary](runs/f3-f2-regression-20261021-01/smoke-summary.json), [environment/source hashes](runs/f3-f2-regression-20261021-01/environment.json) | Pass, all processes exit 0 |
| Known original framing defects | [mutation output](f3_work/f2-mutations.txt) | Both detected; printed failures are intentional mutated-process evidence, tool exit 0 |
| F3 final real processes | [run output](f3_work/final-experiment-run.txt), [summary CSV](runs/f3-finalrepo-20261021-02/summary.csv) | 9 runs, 60/60 observed each, all normal checks true |
| Independent arithmetic/source verification | [raw-timestamp recomputation](f3_work/independent-calculation.json) | 180 samples/mode; current source matches all final manifests |
| Independent review disposition | [review record](f3_work/review.md) | Identified analyzer gaps repaired; final scoped recheck found no remaining issue |

Reproduction from repository root:

```sh
python3 -m unittest discover -s tests -t . -v
python3 -m tests.run_private_smoke --output outputs/runs/new-f2-check
python3 -m tests.check_private_mutations
python3 -m experiments.run_delay --output outputs/runs/new-f3-check
python3 -m experiments.analyze_delay --input outputs/runs/new-f3-check
```

New directories are mandatory. Requested logs are created exclusively. Missing/corrupt logs or nonzero/unclean process termination invalidate a run rather than generating successful summaries. Valid complete evidence with measured loss remains visible and fails normal acceptance.

## Coverage and exact boundaries

| Required behavior | Verification |
| --- | --- |
| Fixed/jitter range, finite bounds, invalid mode/seed and coupled enablement | `test_delay.DelayPolicyTests`; invalid CLI startup retains exit 2 |
| F3 actual implementation/enablement/variant, F1 unavailable | Config/feature/skeleton/real hello tests; server help and metadata |
| Off and enabled fixed-zero preserve chat behavior | Full original F2 suite with F3 off; `test_enabled_zero_delivers_and_logs_measured_zero_path` |
| Only chat is directly delayed, controls retain FIFO | `test_only_chat_waits_and_controls_preserve_fifo`; actual `/enhance` returns startup-only explanation after earlier chat |
| FIFO and distinct accumulated queue time | `test_fifo_queue_time_is_distinct_from_current_wait`; real jitter test; every final experiment also checks FIFO |
| Independent recipient streams and lock-free wait | Seed/interleaving policy test; overlapping actual recipient waits and responsive registration/directory test |
| Full queue/slow consumer isolation and exact admission semantics | Actual 64 queued plus one in-flight delayed frame; overflow gives not_queued, only saturated session closes; healthy recipient succeeds |
| Disconnect/reconnect and shutdown interruption | Real socket cancellation tests, same-name replacement gets no old chat, in-flight discard counted |
| Telemetry failure during F3 wait | [test output](f3_work/f3-log-failure.txt): requested evidence failure detected, server stops; intentionally printed failure notice |
| F2 long messages, split headers/payload/UTF-8, privacy, reconnect, protocol validation | Retained full suite, F2 CLI smoke and deliberate framing mutations |
| Real measured effect and honest accounting | Nine actual runs, strict linked raw logs; no configured delay substituted for elapsed wait |

Raw sender/server/recipient logs and manifests are retained for every final condition/repetition under `outputs/runs/f3-finalrepo-20261021-02`. Earlier nine runs under `…-01` remain developmental evidence and were independently rechecked; final analysis uses only `…-02`. The measured conclusions and precise time/event/denominator definitions are in [F3 analysis](CSE3461_F3_ANALYSIS.md).

## Delivery and limits

[Handoff](CSE3461_F3_HANDOFF.md) contains the change list, exact interfaces, configuration, rollback, coordinator steps, AI contribution and English commit summary/description. [Plan](CSE3461_F3_PLAN.md) records pre-implementation choices and subsequent execution refinements. [Local source review archive](delivery/CSE3461-F3-source-review.zip) contains source, tests, documentation and local evidence, excluding Git internals, bytecode/caches and unrelated workspace files; [archive inventory](delivery/CSE3461-F3-source-review.manifest.json) provides member hashes. This is not a course-named submitted package.

Only Python 3.14.5/macOS localhost was actually exercised. No physical-device/radio measurement, end-to-end recipient acknowledgement protocol, performance-capacity guarantee or synchronized-device-clock claim is made. F1, real-device F1/F2 demonstrations, course report/video/team contribution verification and submissions remain separate. Queue admission and socket-write success still do not prove application receipt; controlled delayed chat can block later control frames. The coordinator should independently inspect/reproduce this F3 delivery before accepting it.
