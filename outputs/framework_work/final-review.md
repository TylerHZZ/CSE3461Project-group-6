# Independent Final Framework Review

2026-10-21 | Reviewer: fresh read-only `final_framework_review` agent | Native implementation

The review below assesses the pre-fix source inventory in `review-package.md`. The parent implementer's disposition and subsequent regression evidence follow the report; no second reviewer pass is claimed.

## Reviewer report

### Strengths

- Registration reply admission and username activation share one short lock; identity-keyed cleanup preserves replacement sessions.
- Transport handles fragmented/coalesced frames, UTF-8 boundaries, idle polling, frame expiry and truncation without assuming one read per message.
- Server writes have a single owner, queues are bounded, and client terminal failures have a separate signal that survives queue overflow.
- Feature gates, defensive handlers and publisher consistently preserve the skeleton-only boundary.
- Acceptance documentation distinguishes localhost evidence, accelerated fault fixtures and deferred device/feature work.

Reviewed the complete implementation and tests. Independently reran 10 non-network tests successfully and reproduced the two findings below with nonmutating probes. The recorded full-suite evidence reports 46 passing tests.

### Critical issues

None found.

### Important issues

1. **A valid registration reply becomes a protocol failure when quit follows registration.**
   **Location:** `cse3461_chat/client.py:214–218`

   Trigger: the client sends `register`, then receives `/quit` or stdin EOF before the registration response arrives. `send('disconnect', {})` changes the state to `CLOSING`. The server correctly responds in FIFO order with `registered` followed by `bye`, but `_apply()` rejects the first response because the state is no longer `AWAITING_REGISTRATION`.

   Reproduced with a controller-level probe: a matching registration response raises `REGISTRATION_CORRELATION` after register → disconnect. This incorrectly diagnoses normal server traffic, aborts the graceful exchange, and marks the completed registration unknown.

   **Fix:** Accept a fully correlated pending registration response while closing, settle that pending request, and preserve `CLOSING` rather than reverting to `REGISTERED`. Add a controlled-peer regression delaying `registered` until after the client sends disconnect.

2. **Rejected registration payloads can persist arbitrary bodies in JSONL.**
   **Location:** `cse3461_chat/dispatch.py:44–46`

   Trigger: a structurally valid registration envelope supplies a non-string username, such as `{"username":{"text":"PRIVATE_BODY"}}`. Validation rejects it, but the rejection path copies the entire unvalidated value into `requested_username`.

   Reproduced with the actual dispatcher and `EventSink`: the JSONL contains the nested `text` object and `PRIVATE_BODY`. This bypasses the documented restriction against logging bodies and allows almost a full frame of arbitrary payload to be persisted as purported username metadata. The existing body-omission test covers only valid feature requests.

   **Fix:** Record only bounded, validated username metadata; use null plus non-content diagnostic metadata for invalid values. Add malformed-registration coverage ensuring nested objects and oversized invalid strings are not copied into logs.

### Minor issues

None raised.

### Declined to judge

- F1/F2 routing, chat publication and F3 A execution: explicitly deferred; their absence is correct.
- Authentication, encryption, reconnect, heartbeat and delivery receipts: excluded from this stage.
- Python 3.12 and physical-device/platform compatibility: not exercised; the handoff accurately identifies these limitations.
- Exit 0 after an explicit orderly server-shutdown bye: considered reasonable for this documented normal lifecycle; distinct from unexpected transport failure.
- Future experiment accuracy/performance conclusions: no experiment is implemented or claimed.

### Readiness assessment

**Ready with fixes.** The foundation is well scoped and substantially verified, but the registration/quit race and malformed-registration logging should be fixed with focused regressions before final acceptance.

## Implementer disposition and verification

Both findings retain **Important** severity by user-visible effect: the first aborts a normal graceful shutdown; the second persists rejected payload content as metadata. Both were fixed in one final pass. No Minor finding was deferred.

- Registration/quit: matching pending registration replies are settled in `CLOSING` without reopening request admission. Controller regression verifies state/pending/unknown outcomes; real CLI regression covers both `/quit` and stdin EOF, correlated bye and exit 0.
- Registration logging: only usernames satisfying the existing 1–24-character ASCII contract are copied. Invalid values become null; the existing error code identifies the failure without payload content. Regression covers nested objects, oversized invalid strings, extra body fields, and a subsequent valid registration.
- [Observed failing regressions](final-fixes-red.txt) → [passing focused regressions](final-fixes-green.txt): 3 tests, including quit/EOF subcases.
- [Final complete suite](final-suite.txt): **49 tests passed**, no failures/errors.
- The five declined areas were assessed and recorded as rulings with their costs in [the ledger](progress.md) and [the handoff](../CSE3461_FRAMEWORK_HANDOFF.md).

Final acceptance is supported by the independent review plus the implementer's observed red/green regressions and full suite. The reviewer did not inspect a second post-fix source snapshot.
