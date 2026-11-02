# Benchmark: offline chain verification of a finished run

`bench_verify_chain.py` runs the real `tools/verify_claim_chain.py` against the
committed `runs/demo` run and requires a `5/5` verdict:

```bash
python benchmarks/bench_verify_chain.py   # RESULT: PASS (exit=0)
```

| Check | What it proves |
|---|---|
| 1. hash chain verifies | `claim_ledger.jsonl` is a valid content-addressed chain (8 records) |
| 2. eight claim fields | every claim row is well-formed |
| 3. evidence hashes | every claim's evidence file hashes to what the ledger recorded |
| 4. gate decisions re-derive | `reproduced 3/3, mismatches 0, unresolvable 0` |
| 5. draft numbers covered | every number in `draft.md` is in the ledger |

This is the honest claim M1 can make: a finished run can be verified from the
outside by reading only its run directory — no model, no network, no writes.
It does **not** claim any research conclusion (see `PREREG.md` §5 boundaries).
