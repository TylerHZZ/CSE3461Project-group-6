# SDD ledger — plan: /Users/nira_def/Documents/ChatGPT/3541 Project 1/outputs/CSE3461_FRAMEWORK_IMPLEMENTATION_PLAN.md

Authorization: 2026-10-21 user reports final coordinator confirmation and explicitly authorizes Native execution of v1.1, skeleton only, followed by S01–S14 and English handoff.

Ruling: Use the existing non-Git workspace and retain this file-based ledger/test evidence instead of Git worktree/commit scripts — the approved plan explicitly excludes repository creation, and no repository exists — cost if wrong: no Git rollback/history; file evidence and final source snapshot remain available.

Pre-flight shared interfaces:
- T1 → T2: Envelope/ProtocolError decoding and immutable WireMessage match; encoding lives in transport.
- T1/T2/T3 → T4: shared result types, channels, immutable limits and EventSink match.
- T4 → T5: manager owns state, queues and lifecycle; directory exposes immutable views only. Package-private runtime helpers will stay in foundation.
- T1/T3/T4 → T5: RequestContext references sessions through postponed annotations to avoid cycles; handlers remain unavailable.
- T1/T2/T3/T5 → T6: client validates server direction/schema before controller-owned correlation/state transitions.
- T1–T6 → T7: acceptance uses real TCP and process tests, preserving unavailable publisher and capabilities.

Tasks: T1 in progress; T2–T7 pending. No existing program/test suite at baseline.

Task 1: complete — protocol suite 3/3; T1-red.txt missing module → T1-green.txt PASS.
Task 2: complete — full suite 9/9; T2-red.txt missing module → T2-green.txt PASS. Partial deadline tests accelerate to 40 ms; idle test waits through the fixed 1-second poll.
Task 3: in progress.

Task 3: complete — full suite 13/13; T3-red.txt → T3-green.txt.
Ruling: Requested log paths must be new files (exclusive creation) — prevents overwriting prior evidence or mixing process runs — cost if wrong: repeated commands must choose a new filename.
Task 4: in progress.

Task 4: complete — full suite 20/20; T4-red.txt → T4-green.txt. Registration race, stale identity, 64-frame overflow and concurrent control-frame ordering verified.
Task 5: in progress. close() requests bounded graceful drain; the writer and runtime supervisor finish resources, avoiding receiver/writer self-join.

Task 5: complete — full suite 29/29 using approved local TCP permission; T5-red.txt → T5-green.txt. Initial sandbox bind EPERM was environmental, not application failure; identical code passed with loopback permission.
Task 6: in progress.

Task 6: complete — full suite 36/36; T6-red.txt → T6-green.txt.
Task 7: in progress. T7-red.txt reproduced two real CLI hangs: main skipped stdin in AWAITING_HELLO; disconnect admission was blocked by a full 32-pending table. Fixed by allowing direct close on quit in those states; T7-green.txt full suite 46/46. No resend or extra pending slot introduced.

Task 7: functional steps complete — 46/46 suite; actual entry-point help; supervised three-client PTY smoke with duplicate-name retry, all unavailable features, Bob reconnect and Ctrl-C shutdown. All five logs valid; no chat/send_result events or text bodies in JSONL. S13 author inspection and S14 README check complete. Fresh final review is the remaining completion gate.

Final review: fresh independent reviewer inspected the full source/test package and reproduced two Important issues. Both retained that grade by actual effect; no Critical or Minor findings. See final-review.md. Single final fix pass; no re-review.

Final: Ruling: F1/F2 routing, chat publication and F3 A remain absent — the authorized deliverable is a connectable skeleton and every feature advertises unavailable — cost if wrong: users cannot exchange chat or run F3 until a later authorized stage.
Final: Ruling: Keep authentication, encryption, automatic reconnect, heartbeat and delivery receipts outside this stage — consistent with the accepted baseline and its documented limits — cost if wrong: this skeleton cannot provide those operational guarantees; an idle partition can remain undetected.
Final: Ruling: Limit verification claims to macOS/Python 3.14.5 and localhost — no Python 3.12, other-platform or physical-device run was performed — cost if wrong: compatibility problems can remain undiscovered until the team runs those environments.
Final: Ruling: Treat an explicit orderly server-shutdown bye as exit 0 — a valid normal lifecycle completed, unlike unexpected transport failure — cost if wrong: callers expecting any remote shutdown to be an error must inspect the reason or change their policy.
Final: Ruling: Make no experiment accuracy or performance conclusion — no F3 experiment is implemented; the shutdown observation is a labeled local lifecycle interval only — cost if wrong: the team still needs separate workload, baseline/treatment and measurement validation.

Final: fixed registration/quit race — test_registration_reply_while_closing_preserves_graceful_quit and test_quit_and_eof_during_registration_exit_cleanly RED→GREEN (including real CLI EOF), suite 49/49.
Final: fixed rejected registration body logging — test_rejected_registration_logs_only_valid_username_metadata RED→GREEN for nested and oversized values, suite 49/49.
Final: minor (deferred): none.

Task 7: complete — final-suite.txt records 49/49 passing; S01–S14, README, English handoff and F1/F2 integration brief finalized. Actual manual evidence remains the pre-final-fix run; the full final suite includes targeted real-process coverage of the changed lifecycle and TCP logging paths. No Git repository, branch, commit, PR or deployment exists; the approved file evidence is retained. Implementation stops at the skeleton boundary.

Repository import, 2026-10-21: the user requested copying the completed development into the existing local `CSE3461Project-group-6` checkout. This supersedes the original non-Git delivery location, not the historical implementation evidence. The import preserves source/tests byte-for-byte, keeps existing LICENSE/.gitignore and team information, makes document links portable, and leaves staging/commit/push to the user. Fresh repository verification is in repository-suite.txt.
