# Repository Guide

## Feature names and branches

Feature numbers follow the course assignment: **F1 = broadcast**, **F2 = private messaging**, **F3 = controlled application delay/jitter**. The earlier local name `f1-one-one` incorrectly labeled private messaging as F1.

| Branch | Purpose | Status |
| --- | --- | --- |
| `main` | Integrated shared framework and F2 private messaging | F2 implementation baseline: `64a0459`; F3 is not merged here |
| `feature/f2-private-chat` | Clearly named branch for the integrated F2 delivery | Created from the documented F2 baseline; no separate reimplementation or pending F2 merge |
| `feature/f3-delay-jitter` | F3 implementation and experiment delivery | F3 implementation baseline: `7fbdbbb`; remains separate from main |
| `archive/f2-standalone` | Original standalone private messaging prototype | Same original commit `1069ff5`; contains known framing bugs; reference only |

`archive/f2-standalone` replaces remote `one-one` and local `f1-one-one`. All original commits are retained. Use the integrated package, not the prototype, for demonstrations and further development.

The F2 branch was created after integration to clarify repository navigation. Its name does not imply F2 still needs merging. Feature completion and course acceptance are separate: physical-device verification and other course deliverables must retain their own evidence.

## Naming convention

- `feature/f<number>-<short-description>` for feature work, such as `feature/f2-private-chat`.
- `fix/<short-description>` for focused repairs.
- `docs/<short-description>` for documentation-only work.
- `archive/<feature>-<description>` for retained obsolete prototypes; do not resume product development there.
- Reserve `main` for deliberately integrated work. Do not merge a feature merely to tidy branch names.

Before development, inspect `git status` and switch to the intended branch. Do not overwrite another workflow's uncommitted changes. Update run instructions and acceptance evidence with behavior changes. Do not rewrite shared history.

## Directory map

| Location | Contents |
| --- | --- |
| `cse3461_chat/` | Supported client/server package and shared infrastructure |
| `cse3461_chat/features/private_chat.py` | F2 recipient selection |
| `cse3461_chat/dispatch.py` | Shared message publication and send results |
| `tests/` | Automated tests and reproducible smoke checks |
| `experiments/` | F3 experiment tooling, available on the F3 branch |
| `outputs/` | Architecture, plans, acceptance reports and handoffs |
| `outputs/runs/` | Captured execution evidence; preserve recorded runs |
| `outputs/framework_work/` | Historical framework development evidence |

Historical evidence and its recorded hashes are not renamed or rewritten during repository organization. Existing `CSE3461_F2_*` and `CSE3461_F3_*` document names already use the correct feature numbers.

## Start here

- [Run and test the application](README.md)
- [F2 handoff](outputs/CSE3461_F2_HANDOFF.md)
- [F2 acceptance](outputs/CSE3461_F2_ACCEPTANCE.md)
- [Shared F1/F2 interface contract](outputs/CSE3461_F1_F2_INTEGRATION_BRIEF.md)
- [Architecture baseline](outputs/CSE3461_ARCHITECTURE_PROPOSAL.md)

On `feature/f3-delay-jitter`, also read `outputs/CSE3461_F3_PLAN.md`, `outputs/CSE3461_F3_ACCEPTANCE.md`, `outputs/CSE3461_F3_ANALYSIS.md` and `outputs/CSE3461_F3_HANDOFF.md`. These files are intentionally not promised on main before F3 integration.

## Updating an older local checkout

After the remote rename, fetch current branch names:

```sh
git fetch origin --prune
```

If your old local prototype branch is named `f1-one-one`, rename it without changing its commits:

```sh
git branch -m f1-one-one archive/f2-standalone
git branch --set-upstream-to=origin/archive/f2-standalone archive/f2-standalone
```

If it is instead named `one-one`, substitute that old local name. Check existing local branches first; do not overwrite an existing archive branch. To work on the corrected F2 version, use `feature/f2-private-chat`, not the archived prototype.
