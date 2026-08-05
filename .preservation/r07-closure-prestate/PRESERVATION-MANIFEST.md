# R-07 CLOSURE CYCLE — COMPLETE WORKTREE PRESERVATION (pre-edit)

> Created by the **fresh R-07 closure builder** session **before any file was modified**.
> It moved no branch, touched no `.git/index`, ran no finalizer, and used no
> `checkout` / `restore` / `stash` / `clean` / `gc` / `prune`.

## 1. What this artifact is

A complete, byte-faithful capture of the primary worktree at the moment the R-07 closure content
cycle began — that is, at metadata commit `06ebfdb35a544df8e9cf36d739cc54a0b6877e1f`, immediately
after the second finalizer and before the R-07 containment record was authored.

It was built through a **HEAD-seeded temporary index** (`git read-tree HEAD` into a
`GIT_INDEX_FILE` outside `.git/index`) — **not** an empty temporary index — so every tracked path
is carried by object identity from `HEAD` rather than re-added from the filesystem.

## 2. Preservation identity

```
preservation ref      refs/preserve/p4-r07-closure-prestate-06ebfdb3
preservation parent   06ebfdb35a544df8e9cf36d739cc54a0b6877e1f
product branch        p4/adapter-containment-completion  (NOT MOVED)
HEAD tree at capture  e3f0c59e36269d541b27d8be8dac8de68234e4fb
```

## 3. Exact path counts at capture

| Class | Count | Captured how |
|---|---|---|
| Tracked files (`git ls-files`) | **622** | **content**, by object identity from the HEAD-seeded index |
| Untracked, non-ignored (reports + sidecars) | **8** | **content**, added from the worktree |
| Tracked-but-ignored (`.playwright-mcp/*`) | **7** | **content** — already inside the 622 (tracked); listed separately for audit |
| Dirty tracked files | **0** | n/a — the worktree tree equals the HEAD tree exactly |
| Index vs HEAD differences | **0** | n/a |
| Ignored-untracked | **18878** | **inventory only** (path · class · size/symlink target · SHA-256) |
| Preservation evidence blobs (this directory) | **9** | content |
| **Total tree entries** | **639** | 622 + 8 + 9 |

**Worktree tree == HEAD tree == `e3f0c59e36269d541b27d8be8dac8de68234e4fb`**, so the tracked half of
this artifact is provably the committed state, not a re-derivation of it.

### 3.1 Why ignored-untracked content is inventoried and not committed

`CLAUDE.md` §10 and the closure tasking both forbid putting secret or environment material into Git
objects. The 18 878 ignored-untracked paths are, by top-level root:

| Root | Paths | Nature |
|---|---|---|
| `.venv/` | 14 445 | build environment — reproducible from `pyproject.toml` |
| `data/` | 3 394 | gitignored working corpora (`active_workspace`, `inbox`, `synthetic_corpus`, downloaded templates) |
| `.chrome-neyma-cdp/` | 761 | a real Chrome profile — **cookies, login data, cached credentials** |
| `eval/` · `src/` · `scripts/` · `configs/` | 267 | `__pycache__`, `*.egg-info`, `eval/results` |
| `.pytest_cache/` | 5 | test cache |
| `.playwright-mcp/` | 2 | untracked siblings of the 7 tracked ones |
| `.env` | 1 | **secrets** |
| `.claude/`, `.DS_Store`, misc | 3 | local tooling |

Every one of the 18 878 is recorded **by path, class, size (or symlink target) and SHA-256** in
[`INVENTORY-ignored-untracked.tsv`](INVENTORY-ignored-untracked.tsv), so the set is fully
enumerable and each file's content is provable after the fact. The single exception is `.env`,
recorded as `SECRET-CLASS / CONTENT-NOT-CAPTURED / OMITTED` — its hash is deliberately not written
into a Git object either. **Nothing is silently dropped: the omission is itself recorded.**

## 4. Sidecar self-verification at capture

All 7 `.sha256` sidecars were re-verified:

| Sidecar | Result |
|---|---|
| `p4-closure-candidate-targeted-adjudication-report-42ea24c.md.sha256` | **MATCH** |
| `p4-closure-candidate-targeted-review-report-42ea24c.md.sha256` | **MATCH** |
| `p4-closure-candidate-targeted-review-handoff-42ea24c.md.sha256` | **MATCH** |
| `p4-final-adjudication-report-0891d1a.md.sha256` | **MATCH** |
| `p4-first-finalization-pass-report-86306d5.md.sha256` | **MATCH** |
| `p4-second-finalization-pass-report-06ebfdb3.md.sha256` | **MATCH** (`96ef5fe8…1fa0`) |
| `p4-independent-rereview-report-0891d1a.md.sha256` | **MATCH under its documented semantics** — the tracked file is 813 lines (a 36-line disarming banner prepended); the sidecar records the **original** preserved report's hash. `tail -n 777` of the tracked file `cmp`s **byte-identical, zero differences** against the blob in `refs/preserve/p4-independent-rereview-0891d1a` and hashes to `181e1a37…b316`, exactly the sidecar's value. Re-derived here, not inherited from the adjudication. |

## 5. Report and canonical-document hashes

Every `docs/implementation/*.{md,yaml,json,sha256}` and the canonical root documents
(`CLAUDE.md`, `README.md`, `AGENTS.md`, `ARCHITECTURE.md`, `PRODUCT.md`,
`docs/CANONICAL-DOCUMENTS.md`, `docs/product/FREIGHT-CAPABILITY-MAP.md`) are hashed in
[`REPORT-AND-CANONICAL-HASHES.txt`](REPORT-AND-CANONICAL-HASHES.txt) — 87 entries.

This includes the reconstructed second-finalization evidence report at its expected value
`96ef5fe85016f2de5d5840814d95dd170947474a3259ac8bb902df9f485a1fa0`, and `CURRENT.md` and every
other canonical document exactly as present at capture.

## 6. Scope

This artifact records state. It certifies nothing, adjudicates nothing, closes no risk and moves no
protected ref. It exists so that the R-07 closure content commit can be compared against the exact
pre-edit worktree by any later reviewer.
