---
name: distill-notify
description: 蒸馏结果的多通道通知：inbox 保底 + 钉钉/Toast/tmux 按环境送达（供 loop-engineer distill 使用）。
---

# distill-notify

## 职责

把蒸馏结果主动送达用户，同时保证失败时信息不丢。

## 执行

```bash
python3 scripts/notify.py --title "蒸馏巡检" --message "<一句话结论>" --digest "digests/2026-08-14.md"
```

## 通知时机

- **有候选待确认** 或 **有 workflow 更新落地** → 通知；
- 无事 → 不通知，只往当日 digest 追加一行。

## 通道

- `inbox`（digests/inbox.md）：保底，任何环境都写；
- `dingtalk`：配置了 webhook+secret 才发（自动加签）；
- `toast`：本机可调 powershell.exe 才弹 Windows 通知；
- `tmux`：在 tmux 会话内才 display-message。

## 失败策略

任何单通道失败只降级不阻断：inbox 一定写，钉钉失败仅告警。
