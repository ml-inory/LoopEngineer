---
name: distill-scan
description: 扫描 Codex 会话目录，维护增量索引并提取蒸馏信号（供 loop-engineer distill 使用）。
---

# distill-scan

## 职责

把 `~/.codex/sessions` 的原始 jsonl 解析为结构化索引，只做确定性工作，不做语义判断。

## 执行

```bash
python3 scripts/scan_sessions.py
```

可选：`--days N` 只看最近 N 天（手动快速巡检用）。

## 产出

- `state/sessions.json`：全量索引（session_id / cwd / family / 时长 / 事件数 / 命令指纹 / 文件指纹 / 首末用户消息 / status）
- `state/scan-report.json`：本次增量（new / appended / unchanged / errors）

## 规则

- 单文件损坏只记入 `errors`，不阻塞全量扫描；
- 索引幂等，可反复运行；
- **禁止读取原始会话内容**，后续阶段只读 `state/` 下的索引与摘要。
