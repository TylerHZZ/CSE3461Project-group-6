# Independent F2 and F3 Acceptance

2026-10-21 | Accepted for the implemented localhost scope and integration into main.

## Reviewed revisions and integration

F2 implementation: `64a0459`; F3 implementation: `7fbdbbb`; reviewed feature tip including navigation: `e59d838`; pre-merge main: `6698852`. F2 was already on main. This integration brings the independently checked F3 implementation into main and records fresh coordinator evidence. No product code was changed during acceptance. The only merge conflict was the README description of whether F3 was implemented; the F3 description and repository navigation were both retained.

The original standalone archive remains at `1069ff5`; it is not a supported runtime. Feature branches remain available for traceability. Earlier handoffs stating uncommitted/unpushed work are historical snapshots superseded by the recorded implementation commits and this integration.

## Fresh verification

- Full suite on the reviewed feature tree: **89/89**, 10.540 seconds, [output](coordinator_acceptance/suite.txt).
- Actual server and CLI clients: **32/32** private smoke checks, [summary](coordinator_acceptance/f2-smoke/smoke-summary.json), [environment and source hashes](coordinator_acceptance/f2-smoke/environment.json).
- Regression credibility: both deliberately injected truncation and one-read framing faults detected, [mutation output](coordinator_acceptance/mutations.txt). Its printed failures are expected and the checker exited 0.
- Fresh real-process F3 experiment: **9/9** runs, **540/540** target-message pairs observed, all processes clean, no sender/observer private receipts, [execution](coordinator_acceptance/f3-experiment.txt), [summary CSV](coordinator_acceptance/f3-experiment/summary.csv). Full manifests and five-process logs are retained under that directory.
- Separate direct computation from raw timestamps and receipt IDs, without the analyzer's metric helpers: [independent metrics](coordinator_acceptance/independent-metrics.json). Source hashes in all nine manifests match the reviewed code.
- Full suite repeated on the merged main tree: **89/89**, 10.618 seconds, [post-merge output](coordinator_acceptance/merged-suite.txt). The command exited 0 before the merge commit was created.

## Independent code review

A separate read-only reviewer examined the F2 route/publisher, framing, privacy, session identity, queues, writer lifecycle, F3 parameters/randomness/cancellation and experiment accounting. No blocking important reproducible defect was found. The reviewer separately reprocessed the implementer's nine original runs and directly recomputed their wait/queue/throughput values; all 540 pairs, source hashes and published results agreed. The coordinator independently executed the new runs above rather than relying on the implementer's report.

Existing regression coverage verifies 300-byte and maximum permitted messages, fragmented headers/payload/UTF-8, coalesced frames, missing/self targets, bystander isolation, same-name reconnect, concurrent senders, full queues, write failures, off/zero F3, FIFO, cancellation and telemetry failure. Queue admission remains distinct from application receipt.

## Fresh measured results

Each mode has 180 frame samples, pooled from three runs with 60 private messages, alternating two recipients. Values below are recalculated from raw logs; receiver rate is a range across six recipient streams, not aggregate server capacity.

| Mode | Actual wait mean ms | Queue mean ms | Queue p95 ms | Recipient messages/s | Observed pairs |
| --- | ---: | ---: | ---: | --- | --- |
| Baseline | 0.000221 | 0.0726 | 0.1025 | 250.09–250.30 | 180/180 |
| Fixed 20 ms | 23.7954 | 291.2426 | 565.3442 | 40.53–41.97 | 180/180 |
| Jitter 5–35 ms | 22.3767 | 272.8749 | 517.8288 | 39.39–50.18 | 180/180 |

Actual elapsed waits can exceed configured waits because of scheduling. Delay increases per-recipient queue residence and lowers observed burst throughput while retaining FIFO. No cross-process clock subtraction or Wi-Fi propagation claim is made. Experimental results are observations of this workload, not a capacity or reliability guarantee.

## Delivery and limits

The supported deliverable is the main-branch source plus tests, experiment tools and current documentation. Python/Markdown whitespace checks and updated document links passed. Existing raw failed-test captures and CSV CRLF line endings trigger broad whitespace warnings; they were retained byte-for-byte as evidence rather than normalized. The earlier `outputs/delivery/CSE3461-F3-source-review.zip` is a historical review snapshot, not the updated authoritative merged repository; its old documentation is not a current status statement.

Acceptance covers macOS/Python 3.14.5 localhost. Physical-device F2 demonstration remains pending; F3 may use simulation under the assignment. F1 remains unimplemented. Other OS/Python versions, student video, report template, genuine student contributions, sharing permissions and course submission are not claimed complete. This merge is acceptance of F2/F3's implemented scope, not acceptance of the whole course project.
