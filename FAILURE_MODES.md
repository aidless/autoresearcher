# Failure modes

Measured on this tree unless a row says it was read from the source. No row is a research finding. The fixture topic string is `does a noise floor bound what a leaderboard can claim`. The votes come from `src/autoresearcher/fixtures/dry_run_experiment.py.in`.

## Gate false pass

A finished run is not "every claim cleared". `GateSegment` stops the chain only when `n_accept == 0`. One ACCEPT is enough for status OK.

Measured on `golden/dry-run` (`gate_decisions.jsonl`):

| claim | decision | verdict | reasons |
|---|---|---|---|
| gate:000 | ACCEPT | READABLE | (empty) |
| gate:001 | ACCEPT | READABLE | (empty) |
| gate:002 | MARGINAL | MARGINAL | `margin +0.0285 is inside the resolution bound 0.0357` |

The CLI printed `status OK` and exited 0. The MARGINAL claim is in the draft under "Unresolved claims". It did not stop the chain.

`LiteratureSegment` has no statistical gate. It returns OK after recording `sources_ok` and `sources_failed`. Measured once, 2026-11-16, by `run_pipeline` with `dry_run=False` in this environment (not re-run in CI; it uses the network, and the count is not a result):

- literature `source` was `live`
- `n_papers` was 20 (`max_results` on the segment)
- `sources_ok` was `['arxiv']`
- `sources_failed` was `semantic_scholar` with an `HTTPError`
- the chain continued and stopped later, at hypothesize

So a failed source did not refuse segment ②. The paper titles from that search are not copied here and are not findings of this repository.

`recompute` calls the same `adjudicate()` as the gate. Agreement does not detect a bug inside `adjudicate`. The empty-hash case below is the measured form of that limit.

## Gate false refusal

`--generators 2` renders the fixture with two label producers. arx's gate then returns `floor_degenerate`, which this package maps to UNDECIDABLE. The claims are the three seeded hypothesis strings, including ones that mention five producers. The apparatus cannot support them, and the chain stops.

Measured by `tools/check_fresh_refusal.py` (re-run on every `make check`) and by the committed snapshot `golden/refused-two-generators`:

```
exit=2
decisions=['UNDECIDABLE', 'UNDECIDABLE', 'UNDECIDABLE']
reasons=['floor_degenerate']
draft=False
stopped=gate
```

The CLI's stderr on the snapshot run was:

```
refused  no claim cleared the gate: every hypothesis in this run is UNDECIDABLE, MARGINAL or REJECT, and a run with nothing readable in it has nothing to hand downstream
```

`python3 tools/verify_claim_chain.py golden/refused-two-generators` exits 1 and prints `4/5`, because check 5 requires `draft.md`. Exit 1 is the same code the tool uses for a broken run. The pipeline's own refusal code is 2. A caller that only reads the verifier cannot tell "refused on purpose" from "broken".

Those three UNDECIDABLE rows do record an evidence sha256. Check 3 passed on the untouched snapshot. Do not confuse this path with the empty-hash path below.

A decimal in `draft.md` that is not in the ledger refuses at self-audit. `tests/test_segments_selfaudit.py::test_an_uncovered_number_in_the_draft_refuses_and_names_the_number` writes `0.9999` into a draft whose ledger row does not contain it, and the segment status is REFUSED with that literal in the reason.

## Ledger tamper limits

The chain is content-addressed. It is not signed. `arx.experiments.ledger.Ledger._sign_record` returns `None`.

| Case | What was done | What the tools said | Test |
|---|---|---|---|
| One-byte edit | Flip one byte of `claim_ledger.jsonl` | `verify_ledger_file` reports `chain_valid` false | `test_flipping_one_ledger_byte_breaks_the_chain` |
| Rewrite and rehash | Change the first record's topic, recompute every hash with `record_hash` | `chain_valid` true, same record count | `test_rewriting_a_payload_and_rehashing_still_verifies` |
| Edit evidence on an ACCEPT run | Add 1 to `duration_s` in `evidence/experiment-000.json` | evidence check fails; `recompute_run` is not ok | `test_an_accept_run_notices_a_changed_evidence_file` |
| Empty evidence hash | `adjudicate` on a result with `returncode` 1, given the file's real sha256 | stored `metrics["evidence_sha256"]` is `""`. After the file is edited, the evidence check still passes and `recompute` reports no mismatch | `test_a_failing_experiment_drops_the_evidence_hash` |

The empty hash is `_undecidable` in `src/autoresearcher/segments/gate.py`: the function is passed `evidence_sha256` and writes the empty string from `_base_metrics` instead. Check 3 skips the comparison when the recorded field is empty, so it does not become a false FAIL, and it also does not see a later edit.

Integer literals are invisible to the draft coverage gate. `NUM_RE` requires a decimal point. `tests/test_audit.py::test_an_integer_absent_from_the_ledger_is_not_flagged` shows that a draft saying `cited 7 times` against metrics that only contain `0.5` produces no uncovered number, while `0.9000` is named.

## Dry-run versus a run without `--dry-run`

Both paths use `offline_config` (`llm_base_url` and `llm_model` empty) and `offline_components`, whose model is `NullLLM`. `NullLLM.available` is false. `--dry-run` does not turn a model on. It only selects the fixture searcher and the three seeded hypotheses.

| | `--dry-run` | without `--dry-run` (one run, 2026-11-16, this environment) |
|---|---|---|
| literature | `source=fixture`, canned `dry_run_papers.json` | `source=live`, `n_papers=20`, arXiv ok, Semantic Scholar `HTTPError` |
| hypotheses | the three seeded strings | `llm=none`, `n_proposed=0`, `n_kept=0` |
| where it stopped | completed (default `--generators 5`) | `hypothesize`, before any experiment |
| refusal | — | `no hypothesis survived de-duplication, so there is nothing to test; a run with nothing to test cannot reach a gate` |
| draft | written from the ledger | none |

That live run is not in CI. Repeating it can change the HTTP error or the paper count. The count 20 is the segment's `max_results`, not a measurement of the literature.

## Known blind spots

1. Anyone who can rewrite the run directory and recompute `record_hash` produces a chain the verifier accepts. There is no external signature.
2. Claims that stop in `_undecidable` (nonzero exit, timeout, failed `validate`, script-hash mismatch, pre-registration failure) store an empty evidence hash. A later edit of that evidence file is not caught by check 3 or by `recompute`.
3. The coverage gate ignores integers, so a draft can cite a whole number the ledger never recorded.
4. `verify_claim_chain` exit 1 covers both "the pipeline refused and wrote no draft" and "the files are corrupt".
5. `recompute` is not a second implementation of the gate.
6. Segment ② does not refuse when a literature source fails.
7. The golden manifest checks a snapshot. A new run's `duration_s` changes the evidence bytes and the ledger hashes, so regeneration is not byte-identical.
8. `env_fingerprint.json` records the producing interpreter. The verifier does not compare it to the machine that rechecks the snapshot.

## Not measured here

- arx's sequential layer and multiplicity layer. They are not called.
- Whether `EvaluationGate`'s READABLE rate is calibrated. This repository does not repeat arx's simulations and does not claim them.
- A second live search, or any run that called a model. No model was called.
