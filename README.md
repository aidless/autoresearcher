# autoresearcher

[![CI](https://github.com/aidless/autoresearcher/actions/workflows/ci.yml/badge.svg)](https://github.com/aidless/autoresearcher/actions/workflows/ci.yml)

> 🗂 **仓库族谱**：「自主研究循环」主线仓是 [ai-researcher](https://github.com/aidless/ai-researcher)（证据链签字版）；本仓定位是逐段统计门禁变体（每段输出过门才能给下一段读）。

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

## 证明什么 / 不证明什么

> 诚实性约束（fail-closed）：本仓证明的是**「闸门是唯一通道」的管道机制**（后段只能读前段已过闸的产物），不证明任何研究结论。

**证明什么**

1. **闸门是唯一通道**：后段读取前段输出的唯一方式是前段写下的 `segment_artifact` 文件；无共享可变状态、无访问邻段结果的 accessor（`src/autoresearcher/segments/base.py`）。生产者拒绝 → 后段无物可跑，而非「必须拒绝使用但有物可用」。
2. **证据链可验证**：`claim_ledger.jsonl` 是哈希链，`verify_claim_chain.py` 只读 run 目录即可复验 5 项（链哈希、八字段、证据哈希、裁决重算、draft 数字覆盖），退出码 `0` 仅当 `5/5`（`tools/verify_claim_chain.py`）。
3. **裁决可重算**：`recompute` 调用与闸门相同的 `adjudicate()`，从证据文件重导每个 gate 决策并与落盘逐字段比对——它只能从文件漂移，不能从闸门漂移。
4. **打包字节确定**：`package` 两次打包同一 run 产出字节相同的 `submission.zip`，可校验而非信任。

**不证明什么**

1. **不证明任何研究结论**：`--dry-run` 是离线确定性演示（`src/autoresearcher/fixtures/dry_run_*.json`），它证明管道**在其输入下正确执行**，不证明「噪声底限制排行榜主张」本身。
2. **不证明模型已接入**：当前 M1 状态是**离线**（①→⑧ 全 CPU）；arx 的 sequential 与 multiplicity 层**刻意不在范围**（README 开头已声明）。
3. **不证明无空跑**：空 ledger 不算通过（`verify_claim_chain` 要求至少 1 条记录）——这是防「空目录 4/5」的机制，不是「有 ledger 就正确」的保证。
4. **不证明免于伪造**：哈希链是**可感知篡改**（内容寻址），不是加密签名；若攻击者能重写整个 run 目录并重算链，外部验证无法区分（`tools/verify_claim_chain.py` 设计如此）。
5. **不证明「拒绝」是 bug**：当 ⑤ 拒绝时管道在 ⑥ 前停止、无 `draft.md`，`verify_claim_chain` 判 `4/5` 且 `researcher run` 退出码 `2`——这是**管道在工作**，不是坏运行（README 已有说明）。

## Benchmark (offline chain verification)

`benchmarks/bench_verify_chain.py` runs the real `tools/verify_claim_chain.py`
against the committed `runs/demo` run and requires a `5/5` verdict:

```bash
python benchmarks/bench_verify_chain.py   # RESULT: PASS (exit=0)
```

It verifies the hash chain (8 records), the eight claim fields, the evidence
hashes, the gate-decision re-derivation (`reproduced 3/3, mismatches 0,
unresolvable 0`), and that every `draft.md` number is covered by the ledger.
This is the honest claim M1 can make: a finished run verifies from the outside
by reading only its run directory — no model, no network, no writes. It does
**not** claim any research conclusion (see `PREREG.md` §5).

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

## Limits and non-goals

Stated from what the code does, not what it might do later:

- **No model is ever consulted in this milestone.** `pipeline.run_pipeline` builds its
  config from `offline_config` (`src/autoresearcher/config.py`), whose empty `llm_*`
  values make arx's `build_llm` return a `NullLLM` — in `--dry-run` *and* without it.
  The dry-run flag only switches the literature searcher and seed hypotheses between
  fixtures and the live searcher; it never enables an LLM.
- **Dry-run evidence is fixture evidence.** `--dry-run` reads canned papers
  (`dry_run_papers.json`), seeded hypotheses, a synthetic leaderboard, and a template
  experiment provider (`src/autoresearcher/dryrun.py`). It exercises the gates; it
  measures nothing about the world and its outputs are not findings.
- **arx's sequential and multiplicity layers are deliberately out of scope** (the
  declared M1 boundary): this repo gates each segment's output statistically; it does
  not implement arx's sequential-correction or multiplicity layers on top.
- **Packaging is not submission.** `package` writes a deterministic `submission.zip`
  and nothing ever submits it — there is no submission transport in this repository.
- **The experiment segment runs a template experiment** (`TemplateExperimentProvider`),
  not a user-supplied research plan; a real experiment loop is future work beyond M1.
