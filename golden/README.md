# Golden snapshots

Two runs produced by this repository's CLI. They are fixtures, not papers.

| Directory | Command | What the tool printed |
|---|---|---|
| `dry-run/` | `python3 -m autoresearcher.cli run --dry-run "does a noise floor bound what a leaderboard can claim" --out golden/dry-run` | status OK, exit 0, then `verify_claim_chain` 5/5 and `recompute` `chain OK \| reproduced 3/3 \| mismatches 0 \| unresolvable 0` |
| `refused-two-generators/` | the same command with `--generators 2` | status REFUSED, exit 2, stopped at `gate`, no `draft.md`. `verify_claim_chain` is 4/5 because check 5 requires a draft. `recompute` still reproduces 3/3. |

`MANIFEST.sha256` is the sha256 of every file under those two directories. `tools/verify_golden.py` recomputes those hashes and re-derives the gate decisions. It does not re-run the pipeline.

Regenerating a run changes `duration_s` inside the evidence files and therefore the ledger hashes. A matching manifest means the snapshot is intact, not that a new run is byte-identical.

`env_fingerprint.json` in each snapshot records the machine that produced it (CPython 3.12.3, linux, x86_64, arx 0.3.0, autoresearcher 0.1.0). Verification does not require the reader's machine to match that fingerprint.

The experiment scripts under each directory are rendered from `src/autoresearcher/fixtures/dry_run_experiment.py.in`. Their votes are synthetic. The numbers in `draft.md` are those votes after the gate, not a measurement of a leaderboard.
