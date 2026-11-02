# PREREG — autoresearcher (M1 · 门控管道机制)

> 预注册规格：本文件声明**本仓库 M1 状态可检验的研究假设、评测方案、
> 成功标准与明确边界**。内容全部对应仓库真实实现与真实输出
> （`src/autoresearcher/` 的 8 段、`tools/verify_claim_chain.py`、
> `runs/demo/claim_ledger.jsonl` 与 `draft.md` 的真实数字、
> `tests/` 的 106 项离线测试、`pyproject.toml` + `.github/workflows/ci.yml`），
> 不含虚构数字或未实现能力。

## 1. 研究问题

一条研究管道中，如何保证**后段只能读前段已过统计闸门的产物**，从而让
「拒绝」成为工具在工作而非故障？核心机制问题：当一段输出无法支撑其主张时，
链必须在下一段读取前停止并明说——拒绝即是工具在工作。

## 2. 假设（H1–H3，全部可证伪）

- **H1（闸门是唯一通道）**：后段读取前段输出的唯一方式是前段写下的
  `segment_artifact` 文件（`src/autoresearcher/segments/base.py`）；无共享
  可变状态、无访问邻段结果的 accessor。生产者拒绝 → 后段无物可跑，而非
  「必须拒绝使用但有物可用」。
- **H2（证据链可验证）**：`claim_ledger.jsonl` 是哈希链；
  `verify_claim_chain.py` 只读 run 目录即可复验 5 项，退出码 `0` 仅当 `5/5`。
- **H3（裁决可重算）**：`recompute` 调用与闸门相同的 `adjudicate()`，从证据
  文件重导每个 gate 决策并与落盘逐字段比对——它只能从文件漂移，不能从
  闸门漂移。

## 3. 评测方案

- **管道**：①→⑤ 产生哈希链 claim ledger；⑥ 写 `draft.md` 通过回读 ledger；
  ⑦ 自审 draft 并可拒绝；⑧ 把完成 run 打包为**确定性归档**（`package` 两次
  打包字节相同）。`--dry-run` 零模型、零网络。
- **验证工具**：`tools/verify_claim_chain.py` 读 run 目录（无管道、无网络、
  无写）复验：链哈希、八字段、证据哈希、裁决重算、draft 数字覆盖。
- **判据**：exit `0` 仅当 `5/5`；exit `1` 否则；exit `2` 未给 run 目录。

## 4. 成功标准

1. `tests/` **106 项全过**（本仓已实现，离线、无 API key）。
2. `verify_claim_chain.py runs/demo` 输出 `5/5`（records=8；
   证据哈希 ok；裁决 `reproduced 3/3 | mismatches 0 | unresolvable 0`；draft 覆盖 ok）。
3. `recompute runs/demo` 输出 `chain OK | reproduced 3/3 | mismatches 0 | unresolvable 0`。
4. `package` 两次打包同一 run 字节相同（确定性归档）。
5. 空 ledger **不算通过**（`verify_claim_chain` 要求 ≥1 条记录）——防「空目录 4/5」。

## 5. 明确边界（不证明什么）

- **不证明任何研究结论**：`--dry-run` 是离线确定性演示（
  `src/autoresearcher/fixtures/dry_run_*.json`），证明管道**在其输入下正确执行**，
  不证明「噪声底限制排行榜主张」本身。
- **不证明模型已接入**：M1 是**离线**（①→⑧ 全 CPU）；arx 的 sequential 与
  multiplicity 层**刻意不在范围**。
- **不证明免于伪造**：哈希链是**可感知篡改**（内容寻址），不是加密签名；
  攻击者若能重写整个 run 目录并重算链，外部验证无法区分（设计如此）。
- **不证明「拒绝」是 bug**：⑤ 拒绝时管道在 ⑥ 前停止、无 `draft.md`，
  `verify_claim_chain` 判 `4/5` 且 `researcher run` exit `2`——这是**管道在工作**。

## 6. 数据与复现

- 复现：
  ```bash
  python3 -m pip install -e ".[dev]"
  python3 -m pytest tests/ -q                          # 106 passed
  python3 -m autoresearcher.cli run --dry-run "does a noise floor bound what a leaderboard can claim" --out runs/demo
  python3 -m autoresearcher.cli verify-ledger runs/demo/claim_ledger.jsonl
  python3 tools/verify_claim_chain.py runs/demo         # 5/5
  python3 -m autoresearcher.cli recompute runs/demo     # 3/3
  ```
