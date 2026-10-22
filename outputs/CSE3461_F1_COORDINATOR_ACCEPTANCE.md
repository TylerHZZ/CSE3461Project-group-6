# Independent F1 F2 F3 Acceptance and Main Integration

2026-10-21 | Coordinator acceptance passed for the implemented localhost scope.

## Revisions and provenance

Reviewed F1 delivery `e21eb9a11f4ae88cdce877d33b1ab9d0d6ec584f`; pre-merge main `8eee99616500ec9eed92b869a2b5f0544ce78597`; teammate original `ee35fe66e0a621750148309c0bdea262cdaca5ef`. The original commit is an ancestor of the integrated delivery. Its broadcast handler blob `95968a4c7cf5ff71b995c80fce90c17a62645f5f` is identical to the delivered handler. Original Git authorship and history remain intact.

The coordinator reviewed the current repository, separately reran tests and real processes, recalculated receipt accounting from raw logs, and commissioned a read-only code review. No blocking issue was found. The merge containing this report integrates the accepted source into main; acceptance changed documentation/evidence only, not product behavior.

## Fresh execution evidence

| Check | Fresh result | Evidence |
| --- | --- | --- |
| Complete suite on feature delivery | 105/105; 15.395 seconds | [suite](coordinator_f1_acceptance/suite.txt) |
| Actual broadcast/private CLIs, F3 off/fixed/jitter | Three modes, 48 checks each; 87/87 selected pairs received exactly once | [runner](coordinator_f1_acceptance/broadcast-smoke.txt), [baseline](coordinator_f1_acceptance/broadcast-smoke/baseline/checked-summary.json), [fixed](coordinator_f1_acceptance/broadcast-smoke/fixed/checked-summary.json), [jitter](coordinator_f1_acceptance/broadcast-smoke/jitter/checked-summary.json) |
| Existing private CLI smoke | 32/32 | [summary](coordinator_f1_acceptance/private-smoke/smoke-summary.json) |
| Deliberate truncation / one-read framing mutations | Both detected; checker exit 0 | [output](coordinator_f1_acceptance/mutations.txt) |
| Original F3 private experiment, independently rerun | 9/9 runs; 540/540 target pairs, zero sender/observer private receipts | [runner](coordinator_f1_acceptance/f3-experiment.txt), [CSV](coordinator_f1_acceptance/f3-experiment/summary.csv) |
| Separate raw-log/hash/provenance verification | All 12 new manifests and receipts agree with source; original history preserved | [independent verification](coordinator_f1_acceptance/independent-verification.json) |
| Complete suite on merged main tree | 105/105; 15.364 seconds; exit 0 before commit | [merged suite](coordinator_f1_acceptance/merged-suite.txt) |

Full manifests, commands, environment, source/log hashes, per-process logs and transcripts are retained alongside the summaries. Mutation-check FAIL text describes intentionally broken in-memory variants, not the unmodified product. No old run has been relabeled as new evidence.

Each broadcast CLI mode selects 28 broadcast target pairs and one private target pair. Exact expected-versus-actual counters confirm all recipients, no duplicates or own broadcast echo, and private isolation. Broadcast actual mean wait was 0.000485 ms with F3 off, 23.179191 ms with fixed 20 ms, and 21.985930 ms with jitter selected in 5–35 ms. These are local elapsed measurements, not configured values substituted for measurements or Wi-Fi latency claims.

## Review and compatibility

The independent reviewer found no important reproducible issue. The production changes add the original broadcast handler plus startup configuration/capability wiring. Shared framing, publisher, sessions/writer, private handler, delay policy and experiment modules are unchanged from the accepted main base. The original two-parent F1 integration preserves both main and teammate history.

Tests cover all eight canonical feature subsets, default-disabled behavior, F3 parameter constraints, full broadcast delivery, no-recipient error, long/Unicode/fragmented/coalesced messages, per-sender FIFO, session snapshots, late join/same-name reconnect, partial/all-unavailable results, queue saturation/healthy-peer isolation, F2 privacy and F3 interruption/zero/fixed/jitter behavior. Valid private errors never fall back to broadcast. Queue results remain admission-only, distinct from client receipts.

## Repository organization

Main is the current integrated product. Feature branches remain as identifiable delivery checkpoints. `archive/f1-original` retains the exact teammate source; `archive/f2-standalone` retains the obsolete private prototype. Original `brodcast-feature` is retained as a documented teammate source branch, not a recommended development or runtime entry point; removal can be coordinated without losing its archived history. Navigation and current handoffs now point to this acceptance; previous F2/F3 and implementer records remain historical evidence.

## Limits

Verified environment: macOS/Python 3.14.5, localhost sockets and actual client/server subprocesses. This establishes scoped functional compatibility, not the absence of all defects. F1 and F2 still require the course's real-device/over-the-air demonstration. F3 simulation is permitted by the assignment. Other OS/Python versions, Teams demonstration, report, actual student contribution statements, sharing and Carmen submission are not claimed complete. Original F1 authorship is retained; AI integration/test work is not attributed to a student.
