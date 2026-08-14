---
name: distill-validate
description: 对蒸馏草稿做结构校验与 holdout 回溯覆盖率验证（供 loop-engineer distill 使用）。
---

# distill-validate

## 职责

用客观门槛挡住次品草稿，不让不合格 workflow 进入激活清单。

## 执行

```bash
python3 scripts/validate_workflow.py --draft state/drafts/<name> [--holdout 2]
```

## 门槛

1. **结构校验**：YAML 可解析、状态机完整（11 态 + 终态）、steps/gates/failure_policy/completion/observability 齐备、SKILL.md frontmatter 匹配、**README.md 存在且含 `# <name>`、`## 用法`、`## 安装与更新`、`## 维护`**；
2. **回溯覆盖率**：留出 holdout 会话，其动作类别（explore/edit/test/fix/commit/ask/validate/synthesize）被 workflow 文本覆盖的比例 ≥ 阈值（默认 0.8）。

## 失败处理

- 结构失败：回 extract 补齐缺失字段，最多重试 2 次；
- 覆盖率不足：检查 step 描述是否过于笼统或缺失阶段，补齐后重验；
- 2 次仍失败：标记 `failed`，丢弃该草稿并记入 `state/drafts/<name>/validation.json`，进通知但不进激活清单。
