# autoresearcher

A research pipeline in which every segment's output has to clear a statistical
gate before the next segment may read it. When a segment cannot support its
output, the chain stops and says so — the refusal is the tool working.

Status: **M1** — segments 1-8 run offline: ①→⑤ produce a hash-chained claim ledger, ⑥ writes
`draft.md` by reading that ledger back, ⑦ self-audits the draft and may refuse, ⑧ packages a
finished run into a deterministic archive. `verify-ledger` verifies any claim's chain. arx's
sequential and multiplicity layers are still deliberately out of scope.

## Install and run

```bash
git clone <this repo>
cd autoresearcher
python3 -m pip install -e ".[dev]"
python3 -m autoresearcher.cli run --dry-run \
    "does a noise floor bound what a leaderboard can claim" --out runs/demo
python3 -m autoresearcher.cli verify-ledger runs/demo/claim_ledger.jsonl
python3 -m autoresearcher.cli recompute runs/demo
```

`--dry-run` consults no model and no network. Everything it prints was produced
by the code in this repository.

## Why the gate is the only passage

A later segment reads an earlier one's output in exactly one way: the file the
earlier segment wrote, named by its `segment_artifact`. There is no shared
mutable state and no accessor that returns a neighbour's result, so a segment
whose producer refused has nothing to run on rather than something it must
decline to use.

## The three artifacts

One command produces three files, and each answers a different question:

| File | Produced by | Answers |
|---|---|---|
| `claim_ledger.jsonl` | ①→⑤ | what was measured, and what the gate decided about each claim |
| `draft.md` | ⑥ | what the run says, with every number read back out of the ledger |
| `gate_decisions.jsonl` | the pipeline | what this run decided — ⑤'s per-claim decisions first, then ⑦'s per-check decisions |

```bash
python3 -m autoresearcher.cli run --dry-run "does a noise floor bound what a leaderboard can claim" --out runs/demo
python3 -m autoresearcher.cli verify-ledger runs/demo/claim_ledger.jsonl
python3 -m autoresearcher.cli package runs/demo
```

`gate_decisions.jsonl` is a projection of the run, not a second hash chain: the ledger's chain
already commits to ⑤'s decisions. ⑦ is a second gate and it may refuse — when a declared check
fails, or when `draft.md` cites a number the ledger never recorded, the chain stops and the run is
not allowed to call itself finished. `package` writes `submission.zip` and never submits: packaging
the same run twice yields a byte-identical archive, so the archive can be checked rather than
trusted.

## Recomputing a decision

```bash
python3 -m autoresearcher.cli recompute runs/demo
```

re-derives every gate decision from the evidence files and the ledger, and
compares the result field by field against what was written down. It calls the
same `adjudicate()` the gate called, so it cannot drift from the gate — only
from the files.

## Verifying a finished run from the outside

```bash
python3 tools/verify_claim_chain.py runs/demo
```

The tool reads a run directory and nothing else — no pipeline, no network, no
writes — and re-checks five things:

| # | Check |
|---|---|
| 1 | the ledger exists and its hash chain verifies |
| 2 | every claim row carries all eight claim fields |
| 3 | every claim's evidence file hashes to what the ledger recorded |
| 4 | every recorded gate decision re-derives from the files |
| 5 | every number in `draft.md` is covered by a value in the ledger |

Output on a complete run:

```
PASS  1. the ledger's hash chain verifies  (records=8)
PASS  2. every claim carries all eight claim fields  (ok)
PASS  3. every claim's evidence hashes to what the ledger recorded  (ok)
PASS  4. every recorded gate decision re-derives from the files  (chain OK | reproduced 3/3 | mismatches 0 | unresolvable 0)
PASS  5. every number in draft.md is covered by the ledger  (ok)
5/5
```

It exits `0` only on `5/5`, exits `1` on anything else, and exits `2` when it is
not given a run directory.

Three things about that output are worth stating rather than leaving to be
guessed at:

- **An empty ledger is not a pass.** The tool requires the ledger to exist and to
  hold at least one record. arx calls an absent ledger a valid *empty* chain
  (`chain_valid=True, records=0`), which is true and useless: a directory holding
  no run at all would otherwise clear check 1 and score `4/5`.
- **A claim with an empty evidence hash is not a broken claim.** ⑤'s
  `_undecidable` path records no digest, so check 3 still requires that claim's
  evidence anchor to resolve but does not compare the file against the empty
  string — that comparison would fail for a reason that is not a finding.
- **A run that refused has no draft, and the tool says so.** When ⑤ refuses, the
  chain stops before ⑥ and there is no `draft.md` by design, so check 5 fails and
  the verdict is `4/5`. That is the pipeline working, not a broken run:
  `researcher run` exits `2` and still writes `gate_decisions.jsonl` for exactly
  that case.
