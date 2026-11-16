# Benchmark: offline chain verification of a finished snapshot

`bench_verify_chain.py` runs `tools/verify_claim_chain.py` against the committed
`golden/dry-run` snapshot and requires a `5/5` verdict:

```bash
python benchmarks/bench_verify_chain.py   # RESULT: PASS only when the snapshot is 5/5
```

The snapshot is a `--dry-run` fixture. A 5/5 verdict means the hash chain, the
eight claim fields, the evidence hashes, the re-derived gate decisions, and the
draft's decimal coverage all match the files. It does not mean the fixture
measured a leaderboard. See `FAILURE_MODES.md`.
