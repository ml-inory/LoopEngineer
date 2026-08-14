#!/usr/bin/env python3
"""为指定候选簇/单会话生成蒸馏草稿骨架（模板 + 摘要引用）。

输出：state/drafts/<name>/
  - skills/<name>/SKILL.md      入口 skill 模板（Agent 填充）
  - workflows/<name>.yaml       标准 LoopEngineer spec 模板（Agent 填充）
  - README.md                   给人看的说明（Agent 填充）
  - session_summaries.md        该簇会话的紧凑摘要
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import STATE_DIR, ensure_dirs  # noqa: E402


SKILL_TEMPLATE = """---
name: {name}
description: {description}
---

# {name}

> 本 skill 由 LoopEngineer 从 {count} 个同类 Codex 会话中蒸馏生成（{date}）。
> 权威工作流协议见 `workflows/{name}.yaml`；每阶段读取对应 hidden helper。

## 阶段速查表

<!-- Agent 蒸馏时填写：阶段 / 执行方式 / 验证要点 / STOP 条件 -->

| 阶段 | 执行方式 | 验证要点 | STOP |
|------|----------|----------|------|
|      |          |          |      |

## 经验约定

<!-- 蒸馏出的长期经验：日志只读尾部、临时文件清理、禁止读取二进制产物等 -->

## 断点续跑

<!-- 状态文件位置与恢复方式 -->
"""


WORKFLOW_TEMPLATE = """workflow:
  schema_version: "1.0"
  name: {name}
  entry_skill: {name}
  mode: guided
  task_type: deterministic
  visibility: collapsed_by_default
  requirement:
    goal: ""            # TODO 蒸馏时填写
    output:
      format: ""
      destination: ""
      consumer: "human"
    constraints: {{}}
    acceptance:
      checks: []        # TODO 蒸馏时填写
    assumptions: []
    open_questions: []
  capabilities: []
  inputs: []
  outputs: []
  state_machine:
    initial: draft
    states: [draft, awaiting_user, ready, running, validating, retrying, rolling_back, degraded, blocked, failed, succeeded]
    terminal: [blocked, failed, succeeded]
    transitions:
      - from: draft
        to: ready
        when: "requirements and required capabilities are sufficient"
      - from: ready
        to: running
        when: "execution starts"
      - from: running
        to: validating
        when: "all required execution steps finish"
      - from: validating
        to: succeeded
        when: "all acceptance checks pass"
      - from: validating
        to: retrying
        when: "a recoverable check fails and retry budget remains"
      - from: retrying
        to: running
        when: "repair step is scheduled"
      - from: running
        to: rolling_back
        when: "a failure requires rollback"
      - from: rolling_back
        to: failed
        when: "rollback completes and no retry path remains"
      - from: running
        to: blocked
        when: "required external input, permission, or credential is unavailable"
  steps: []             # TODO 蒸馏时按阶段填写（id/kind/skill/depends_on/inputs/outputs/retry/on_failure）
  gates: []             # TODO 蒸馏时填写 STOP / 门禁
  failure_policy:
    default_action: fail
    max_total_attempts: 3
    rollback_required_for: []
    ask_user_for: []
    degraded_output_allowed: false
  observability:
    progress_updates: milestone
    audit_log:
      enabled: true
      include_hidden_steps: true
  completion:
    success_when: []
    failure_when: []
"""


README_TEMPLATE = """# {name}

{description}

> 本 workflow 由 LoopEngineer 从 {count} 个同类 Codex 会话中蒸馏生成（{date}）。
> 权威协议见 `workflows/{name}.yaml`；Agent 执行入口见 `skills/{name}/SKILL.md`。

## 这是什么

<!-- 给人类看的用途说明：解决什么问题、什么时候用、什么时候不该用 -->

## 用法

<!-- 怎么触发/调用：入口 skill、需要的输入、典型示例 -->

## 输入与输出

| 输入 | 说明 |
|------|------|
|      |      |

| 输出 | 位置 |
|------|------|
|      |      |

## 安装与更新

```bash
# 安装/更新到 Codex
bash <awesome-skills 仓库>/setup.sh --codex
# 或 Claude Code
bash <awesome-skills 仓库>/setup.sh --claude
```

## 目录结构

```text
skills/{name}/SKILL.md      Agent 执行入口
workflows/{name}.yaml       权威 workflow 协议（状态机/步骤/门禁/失败策略）
README.md                   本说明（给人看）
CHANGELOG.md                变更日志（apply 时自动追加）
```

## 维护

<!-- 更新方式：走 LoopEngineer 蒸馏 update 流程；改动需同步 SKILL.md 与 YAML；落地自动写 CHANGELOG -->
"""


def slugify(name: str) -> str:
    return re.sub(r"[^a-z0-9-]+", "-", name.strip().lower()).strip("-") or "untitled"


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--cluster-id", required=True, help="candidates.json 中的 cluster_id 或 high_value_singles")
    ap.add_argument("--name", required=True, help="蒸馏产物名（小写连字符）")
    ap.add_argument("--description", default="", help="入口 skill 的一句话描述")
    args = ap.parse_args()
    ensure_dirs()

    cand_file = STATE_DIR / "candidates.json"
    if not cand_file.exists():
        print("error: state/candidates.json not found; run cluster_sessions.py first", file=sys.stderr)
        return 1
    cand = json.loads(cand_file.read_text(encoding="utf-8"))
    cluster = next((c for c in cand["clusters"] if c["cluster_id"] == args.cluster_id), None)
    single = next((s for s in cand["high_value_singles"] if s["session_id"] == args.cluster_id), None)
    if cluster is None and single is None:
        print(f"error: unknown cluster/single: {args.cluster_id}", file=sys.stderr)
        return 1

    name = slugify(args.name)
    source = cluster or single
    hits = source.get("existing_hits", [])
    if hits:
        hit_names = {h["name"] for h in hits}
        if name not in hit_names:
            print(
                f"error: 候选命中已有 workflow（{', '.join(sorted(hit_names))}），不能另起新名 {name}；"
                "更新时请使用 --name <已有名>，否则应 skip",
                file=sys.stderr,
            )
            return 2
        if not any(h["in_awesome"] for h in hits):
            print(
                "error: 候选命中项目/已安装目录里的已有 workflow，不在 awesome-skills，"
                "不应重复蒸馏到 awesome-skills；应 skip",
                file=sys.stderr,
            )
            return 2

    dec_file = STATE_DIR / "cluster-decisions.json"
    if dec_file.exists() and hits:
        decisions = json.loads(dec_file.read_text(encoding="utf-8")).get("decisions", [])
        for d in decisions:
            if d.get("cluster_id") == args.cluster_id and d.get("action") == "new":
                print(
                    f"error: {args.cluster_id} 命中已有 workflow，cluster-decisions.json 却标记为 new；"
                    "请改为 update 或 skip",
                    file=sys.stderr,
                )
                return 2

    count = cluster["count"] if cluster else 1
    sessions_file = STATE_DIR / "sessions.json"
    sessions = json.loads(sessions_file.read_text(encoding="utf-8")).get("sessions", {}) if sessions_file.exists() else {}
    member_ids = cluster["session_ids"] if cluster else [single["session_id"]]

    draft = STATE_DIR / "drafts" / name
    skill_dir = draft / "skills" / name
    wf_dir = draft / "workflows"
    skill_dir.mkdir(parents=True, exist_ok=True)
    wf_dir.mkdir(parents=True, exist_ok=True)

    from datetime import date

    (skill_dir / "SKILL.md").write_text(
        SKILL_TEMPLATE.format(name=name, description=args.description or f"由 {count} 个同类会话蒸馏的工作流", count=count, date=date.today().isoformat()),
        encoding="utf-8",
    )
    (wf_dir / f"{name}.yaml").write_text(WORKFLOW_TEMPLATE.format(name=name), encoding="utf-8")
    (draft / "README.md").write_text(
        README_TEMPLATE.format(name=name, description=args.description or f"由 {count} 个同类会话蒸馏的工作流", count=count, date=date.today().isoformat()),
        encoding="utf-8",
    )

    lines = [f"# {name} 蒸馏素材（{count} 会话）", ""]
    for sid in member_ids:
        s = sessions.get(sid, {})
        lines.append(f"## {sid}")
        lines.append(f"family={s.get('family')} events={s.get('events')} span_h={s.get('span_hours')} msgs={s.get('user_message_count')}")
        lines.append("命令: " + ", ".join(s.get("commands", [])[:15]))
        lines.append("文件: " + ", ".join(s.get("files", [])[:15]))
        lines.append("首条: " + (s.get("first_user_message") or "")[:400])
        lines.append("末条: " + (s.get("last_user_message") or "")[:200])
        lines.append("")
    (draft / "session_summaries.md").write_text("\n".join(lines), encoding="utf-8")
    print(f"draft scaffolded: {draft}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
