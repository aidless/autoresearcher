# autoresearcher

A research pipeline in which every segment's output has to clear a statistical
gate before the next segment may read it. When a segment cannot support its
output, the chain stops and says so — the refusal is the tool working.

Status: **M1** — segments 1-7 run offline: ①→⑤ produce a hash-chained claim ledger, ⑥ writes
`draft.md` by reading that ledger back, ⑦ self-audits the draft and may refuse. `verify-ledger`
verifies any claim's chain. Submission packaging (⑧) and the standalone third-party verifier
arrive later in this milestone; arx's sequential and multiplicity layers are still deliberately
out of scope.

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
```

`gate_decisions.jsonl` is a projection of the run, not a second hash chain: the ledger's chain
already commits to ⑤'s decisions. ⑦ is a second gate and it may refuse — when a declared check
fails, or when `draft.md` cites a number the ledger never recorded, the chain stops and the run is
not allowed to call itself finished.

## Recomputing a decision

```bash
python3 -m autoresearcher.cli recompute runs/demo
```

re-derives every gate decision from the evidence files and the ledger, and
compares the result field by field against what was written down. It calls the
same `adjudicate()` the gate called, so it cannot drift from the gate — only
from the files.
