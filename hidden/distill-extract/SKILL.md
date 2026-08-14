---
name: distill-extract
description: 从候选簇的会话摘要中提取阶段/门禁/回退/经验，起草 workflow 与 SKILL.md（供 loop-engineer distill 使用）。
---

# distill-extract

## 职责

把会话中隐含的“做事套路”显式化为可执行的 workflow 产物。这一步是纯 LLM 语义工作，脚本只负责搭骨架。

## 执行

1. 读取 `state/cluster-decisions.json` 与 `state/cluster-summaries.md`（或 `state/drafts/<name>/session_summaries.md`）；
2. 生成骨架：

```bash
python3 scripts/extract_workflow.py --cluster-id c1 --name <name> --description "一句话描述"
```

3. 填充 `state/drafts/<name>/skills/<name>/SKILL.md`：
   - 阶段速查表（阶段 / 执行方式 / 验证要点 / STOP 条件）；
   - **经验约定**：从会话里提炼的长期经验（日志只读尾部、临时文件清理、禁止读二进制产物等）；
   - 断点续跑方式；
4. 填充 `state/drafts/<name>/README.md`（给人看的说明，不是给 Agent 的）：
   - 这是什么：用途、适用场景、什么时候不该用；
   - 用法：如何触发/调用、所需输入、典型示例；
   - 输入与输出；
   - 安装与更新：`setup.sh --codex / --claude`；
   - 维护：更新走 distill update 流程、改动需同步 SKILL.md 与 YAML、落地自动写 CHANGELOG。
5. 填充 `state/drafts/<name>/workflows/<name>.yaml`：
   - `steps`：每阶段一个 step（id/kind/depends_on/retry/on_failure）；
   - `gates`：STOP / 审批 / 验证门禁；
   - `failure_policy`：会话中出现的重试/回退/降级模式；
   - `completion.success_when`：会话实际验证过的检查项。

## 规则

- 每阶段在会话摘要里有据可依才写，禁止编造步骤；
- 经验约定是蒸馏产物区别于普通计划的灵魂，必须写；
- README 必须写给人类：读完能知道这个 workflow 解决什么问题、怎么用、怎么维护；
- 产物必须可解释：读完 SKILL.md 能重建会话的做事顺序；
- 候选带 `existing_hits` 时禁止新建：`in_awesome=true` 才允许用同名做 update，
  `in_awesome=false` 直接 skip，`extract_workflow.py` 会拒绝违反该规则的调用。
