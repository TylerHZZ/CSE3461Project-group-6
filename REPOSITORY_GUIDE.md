# Repository Guide

## Feature names and branches

Feature numbers follow the course assignment: **F1 = broadcast**, **F2 = private messaging**, **F3 = controlled application delay/jitter**. The earlier local name `f1-one-one` incorrectly labeled private messaging as F1.

| Branch | Purpose | Status |
| --- | --- | --- |
| `main` | Integrated shared framework, F1 broadcast, F2 private messaging and F3 delay/jitter | F1 integration `e21eb9a`, F2 baseline `64a0459` and F3 baseline `7fbdbbb`; independently accepted and integrated |
| `feature/f1-broadcast` | Teammate F1 integrated with current F2/F3 | Independently accepted and integrated into main; branch retained for traceability |
| `feature/f2-private-chat` | Clearly named branch for the integrated F2 delivery | Created from the documented F2 baseline; no separate reimplementation or pending F2 merge |
| `feature/f3-delay-jitter` | F3 implementation and experiment delivery | F3 implementation baseline: `7fbdbbb`; retained after integration into main |
| `archive/f1-broadcast` | Exact original teammate F1 commit `ee35fe6` | Source backup with full history; no defect or obsolescence claim |
| `archive/f2-private-chat` | Original standalone private messaging prototype | Same original commit `1069ff5`; contains known framing bugs; reference only |

Archive names use the same feature suffix as development branches. `archive/f1-broadcast` replaces `archive/f1-original` and the misspelled duplicate `brodcast-feature`; all three referred to original commit `ee35fe6`. `archive/f2-private-chat` replaces `archive/f2-standalone` and retains `1069ff5`. Only branch names changed; no source history was deleted. Historical evidence keeps the names recorded at execution time.

The F2 branch was created after integration to clarify repository navigation. Its name does not imply F2 still needs merging. Feature completion and course acceptance are separate: physical-device verification and other course deliverables must retain their own evidence.

## Work ownership

Aaditya authored original F1 commit `ee35fe6`. The authorized F1 integration on `feature/f1-broadcast` retains that commit and its handler unchanged, reconciles startup wiring with F3, and adds tests/evidence. F1/F2/F3 have now passed coordinator independent localhost acceptance and are integrated into main. Git authorship does not establish the full student contribution report.

## Naming convention

- `feature/f<number>-<short-description>` for feature work, such as `feature/f2-private-chat`.
- `fix/<short-description>` for focused repairs.
- `docs/<short-description>` for documentation-only work.
- `archive/<feature>-<description>` for retained source snapshots/prototypes; read each branch status before use. An archive name does not by itself imply a defect.
- Reserve `main` for deliberately integrated work. Do not merge a feature merely to tidy branch names.

Before development, inspect `git status` and switch to the intended branch. Do not overwrite another workflow's uncommitted changes. Update run instructions and acceptance evidence with behavior changes. Do not rewrite shared history.

## Directory map

| Location | Contents |
| --- | --- |
| `cse3461_chat/` | Supported client/server package and shared infrastructure |
| `cse3461_chat/features/broadcast.py` | F1 lookup-time recipient snapshot |
| `cse3461_chat/features/private_chat.py` | F2 recipient selection |
| `cse3461_chat/dispatch.py` | Shared message publication and send results |
| `tests/` | Automated tests and reproducible smoke checks |
| `experiments/` | F3 experiment tooling, integrated into main |
| `outputs/` | Architecture, plans, acceptance reports and handoffs |
| `outputs/runs/` | Captured execution evidence; preserve recorded runs |
| `outputs/framework_work/` | Historical framework development evidence |

Historical evidence and its recorded hashes are not renamed or rewritten during repository organization. Existing `CSE3461_F2_*` and `CSE3461_F3_*` document names already use the correct feature numbers.

## Start here

- [Run and test the application](README.md)
- [F1 integration handoff](outputs/CSE3461_F1_HANDOFF.md) and [implementer evidence](outputs/CSE3461_F1_ACCEPTANCE.md)
- [F2 handoff](outputs/CSE3461_F2_HANDOFF.md)
- [F2 acceptance](outputs/CSE3461_F2_ACCEPTANCE.md)
- [Shared F1/F2 interface contract](outputs/CSE3461_F1_F2_INTEGRATION_BRIEF.md)
- [Architecture baseline](outputs/CSE3461_ARCHITECTURE_PROPOSAL.md)

On main and `feature/f3-delay-jitter`, also read `outputs/CSE3461_F3_PLAN.md`, `outputs/CSE3461_F3_ACCEPTANCE.md`, `outputs/CSE3461_F3_ANALYSIS.md` and `outputs/CSE3461_F3_HANDOFF.md`. These files are now included on main following independent acceptance.

## Updating an older local checkout

Run `git fetch origin --prune` to refresh remote names and remove stale remote-tracking references. Local feature branches track their identically named `origin/feature/...` branches. Local archive branches track their identically named `origin/archive/...` branches. The `origin/` prefix indicates a remote-tracking reference, not a second naming convention.

If you still have the old local archive names, and no branch already uses the new name:

```sh
git branch -m archive/f1-original archive/f1-broadcast
git branch --set-upstream-to=origin/archive/f1-broadcast archive/f1-broadcast
git branch -m archive/f2-standalone archive/f2-private-chat
git branch --set-upstream-to=origin/archive/f2-private-chat archive/f2-private-chat
```

An older `f1-one-one` or `one-one` local branch is the F2 prototype, not F1. Check its commit before renaming it to `archive/f2-private-chat`; do not overwrite an existing local branch. Use main for the current integrated product, feature branches for retained delivery checkpoints, and archives for source history.

## Independent acceptance

See [current F1/F2/F3 coordinator acceptance](outputs/CSE3461_F1_COORDINATOR_ACCEPTANCE.md) for fresh tests, experiments, scope and remaining course requirements. [Earlier F2/F3 acceptance](outputs/CSE3461_COORDINATOR_ACCEPTANCE.md) remains historical. Feature branches are retained for traceability.
