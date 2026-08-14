---
name: distill-cluster
description: 基于动作指纹把会话聚成候选簇，LLM 命名并决定 new/update/skip（供 loop-engineer distill 使用）。
---

# distill-cluster

## 职责

在确定性聚类结果之上做语义判断：起名、过滤噪音、区分“新建 workflow”与“更新已有 workflow”。

## 执行

1. 运行 `python3 scripts/cluster_sessions.py`，读取 `state/candidates.json` 与 `state/cluster-summaries.md`；
2. 对每个簇做语义鉴别：
   - 该簇会话在干什么？（看首条消息、顶层命令、相关文件）
   - 是否命中 `existing_workflows` 已有产物？命中 → `update`；否则 → `new`；
   - 明显无关的并簇（同目录但任务不同）→ 拆开或标记 `skip`；
3. 高价值单会话：信息量足够大（跨天、长会话、深度迭代）→ 标记可蒸馏；否则 `skip`；
4. 把最终决定写入 `state/cluster-decisions.json`：

```json
{"decisions": [{"cluster_id": "c1", "action": "new|update|skip", "name": "workflow 名", "target": "awesome-skills 里已有 workflow 名"}], "singles": [...]}
```

## 规则

- 簇名用小写连字符（如 `ax-model-convert`）；
- 拿不准的一律 `skip` 并写一句原因，不硬蒸；
- 同簇会话数 < 2 且非高价值 → `skip`。
- **`existing_hits` 是硬约束**（脚本已从 awesome-skills、Codex/Claude 已安装 skill、
  以及会话文件反推的 workflow 引用算出）：
  - `in_awesome=true` → `update`，名字必须与已有 workflow 完全一致；
  - `in_awesome=false`（项目内 workflow / 已安装 skill）→ `skip`，禁止 `new`，
    禁止另起新名重复蒸馏；
  - 任何情况下不得给命中已有 workflow 的候选起新名字。
- 高价值单会话命中 `existing_hits` 时同样按上一条处理，不因“信息量大”就重复蒸。
