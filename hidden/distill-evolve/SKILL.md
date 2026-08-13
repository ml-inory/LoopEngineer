---
name: distill-evolve
description: 把命中已有 workflow 的新会话提炼为增量更新提案，按风险分级应用（供 loop-engineer distill 使用）。
---

# distill-evolve

## 职责

让已有 workflow 随新会话“进化”，而不是推倒重蒸。

## 执行

1. 对决策为 `update` 的簇，读取 `state/cluster-summaries.md` 中该簇的增量内容；
2. 只提取**增量**：
   - 新出现的失败模式 → 补进 `failure_policy` 或对应 step 的 `retry/on_failure`；
   - 新验证手段 → 补进 `gates` / `completion.success_when`；
   - 新经验 → 补进 SKILL.md 的“经验约定”；
   - 会话中出现、现有 workflow 完全没有的步骤 → 补新 step；
3. 更新草稿后验证（走 distill-validate）；
4. 应用：

```bash
python3 scripts/apply_workflow.py --draft state/drafts/<name> --update --confirm
```

## 风险分级

- **纯增量**（只加步骤/经验/门禁，不删不改旧行为）→ 可自动应用（`--auto`）；
- **结构性改动**（删/改旧步骤、改失败策略）→ 必须用户确认，写入 `digests/inbox.md` 待确认；
- 更新落地必须产生 awesome-skills 仓库 commit（git 历史即回滚点）。
