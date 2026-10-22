# F1 broadcast integration plan

2026-10-21 | Authorized implementation on feature/f1-broadcast; independent coordinator acceptance remains separate.

## Binding design

Integrate the teammate's existing recipient handler into main 8eee99616500ec9eed92b869a2b5f0544ce78597. Source: ee35fe66e0a621750148309c0bdea262cdaca5ef (Aaditya), parent 64a0459. Preserve the exact original commit through a merge and archive/f1-original; keep brodcast-feature untouched. No main push or merge. The old ChatGPT project copy is not a source.

Use the existing directory snapshot, publisher, framing, queues and sole writers. F1 selects other registered/non-closing session IDs, returns NO_RECIPIENTS when empty, never echoes and never re-resolves names. One publication UUID and admission-only queued/partial/not_queued counts. Preserve F2 privacy and F3 per-recipient FIFO, cancellation, seeded delays and startup validation. Default none; permit the eight canonical ascending feature subsets. F3 still requires fixed/jitter mode. No unrelated refactor or wire change.

## Execution tasks

1. Baselines and provenance: check actual repo/remote/AGENTS, create and push feature branch before implementation, archive original tip, export exact source into isolated temporary directory. Run original and main suites. Add independent boundary tests and run against original; record observed limitations without inventing defects.
2. Merge: add new compatibility tests and observe main's missing F1 behavior. Merge original with history; resolve config/capability/server/docs/test conflicts by combining valid F1 changes with current F3. Keep broadcast handler byte-identical to source. Run targeted plus full suite.
3. Evidence: run real F1 CLI broadcast checks with at least three clients in baseline, fixed and jitter modes; preserve process logs, exact receipts, manifests, source hashes, exit codes, FIFO/no-echo/private isolation checks. Rerun unchanged F3 nine-run private experiment/analyzer, F2 CLI smoke and framing mutation checks. Deterministic socket tests cover snapshot/reconnect, simultaneous senders, fragmentation, Unicode and queue saturation/cancellation.
4. Delivery: update current README/guide/framework/interface status; retain historical acceptance documents. Write F1 HANDOFF and implementer ACCEPTANCE with contribution distinction, matrix and unverified device/course scope. Obtain fresh code review, resolve material findings, verify final tree, commit/push only feature branch. Recheck remote source/main for movement and list original spelling cleanup for coordinator confirmation only.

## Review focus

- Mixed send_result and incoming broadcasts under simultaneous senders; per-sender order without global order claims.
- Captured recipient departure, all departed, new join and same-name replacement before publish.
- Full/slow one-recipient queue while other broadcast recipients progress; queued versus received distinction.
- All eight feature combinations and F3 mode validation; default disabled still enforced.
- Raw actual-process receipt evidence must match selected target pairs; no localhost-to-device claims.

## Execution ledger

- Repository and remote clean at stated main/source hashes; no applicable AGENTS.md found.
- feature/f1-broadcast created and upstream set before implementation; archive/f1-original points to exact original source; brodcast-feature unchanged.
- Baselines: original suite 69/69, main suite 89/89. Initial shell wrapper used a reserved zsh variable after tests; tests themselves completed with OK, raw outputs retained. Subsequent wrappers use f1_test_rc.
- Process ruling: user's explicit planning/implementation/testing/push authorization supplies execution approval; proceed inline on the requested feature branch. Source preservation takes precedence over any skill suggestion to rewrite existing code.
- Original extended suite: 6/6 passed. No observed original F1 routing defect; preserve handler exactly.
- Three-way merge conflicts in README/config/handler table/server status/private smoke/feature tests/skeleton tests resolved by combining F1 wiring with main F3. Additional F3 test assertion still expected F1 unimplemented; updated only that status assertion. Full suite then passed 105/105.
- All eight feature subsets exercised through actual server requests; fixed/jitter/off rules retained. F1-only+F3 and all-feature combinations exercised separately.
- Broadcast CLI first developmental run communicated successfully but failed evidence aggregation because the new script used session_id instead of the existing receiver_session_id field. Corrected the harness; no production change. Subsequent three conditions each passed 48 checks and received 29/29 target pairs. Both the failed and successful captures are retained.
- Unchanged F2 CLI smoke passed 32/32; known framing mutations both caught (expected printed assertion failures). Unchanged F3 experiment runner/analyzer passed 9/9 with 540/540 actual receipts. All 12 successful run source/log manifests verified against the current files.
- Final fresh read-only code review: no Critical/Important/Minor findings; reviewer reran 15 focused tests and independently matched original-handler bytes and all broadcast source/log/receipt hashes. Review exclusions (documents, parent F2/F3 reruns, devices/other environments/course) are covered by implementer document/evidence checks or explicitly left unverified in the handoff.
- Final disposition follows the user's chosen feature-branch push and stop-for-coordinator workflow; no main merge, PR creation or original-branch deletion is authorized by this delivery.
- Final precommit suite: 105/105 in 15.426 seconds; no unresolved conflicts. Remote main and original source still match the authorized starting hashes. No deferred review findings.
