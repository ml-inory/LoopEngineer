# Loop Engineer

Loop Engineer is an agent workflow protocol for turning ambiguous user requests
into structured, auditable, and recoverable workflows.

The project is centered on [`SKILL.md`](./SKILL.md). That skill defines how an
agent should clarify requirements, inventory capabilities, design a workflow DAG,
handle retries and rollback, and decide when user approval is required.

Since the `evolution` branch, LoopEngineer also ships a **distill mode**
(`$loop-engineer distill`): it scans Codex session history, detects repetitive
work, and distills it into installable, self-evolving workflows under
`~/Codes/awesome-skills`. See [`REQUIREMENTS.md`](./REQUIREMENTS.md) for the
aligned design and [`workflows/distill.yaml`](./workflows/distill.yaml) for the
distiller's own workflow spec.

## 安装自动蒸馏器

蒸馏器会在每天 07:00 / 23:00 自动巡检 Codex 会话，发现重复性工作后蒸馏成
workflow 并安装到 `~/Codes/awesome-skills`。手动也可以随时触发。

### 1. 安装入口 skill

```bash
./install.sh          # 同时安装到 ~/.codex/skills 与 ~/.claude/skills
```

安装后重启 Codex，使 `$loop-engineer distill` 生效。

### 2. 配置

```bash
cp config/distill.env.example config/distill.env
# 编辑 config/distill.env（已被 gitignore，含密钥也安全）
```

关键配置：

| 键 | 必填 | 说明 |
|-----|------|------|
| `CODEX_SESSIONS_DIR` | 是 | Codex 会话目录，默认 `~/.codex/sessions` |
| `AWESOME_SKILLS_DIR` | 是 | 蒸馏产物仓库路径，默认 `~/Codes/awesome-skills` |
| `AWESOME_SKILLS_REPO` | 否 | 产物仓库缺失时自动 clone 的地址 |
| `DINGTALK_WEBHOOK` / `DINGTALK_SECRET` | 否 | 钉钉手机推送（群机器人 + 加签） |
| `PUSHPLUS_TOKEN` | 否 | PushPlus 备选推送，留空即可 |
| `CLUSTER_MIN_SESSIONS` / `COVERAGE_THRESHOLD` | 否 | 聚类门槛 / 验证覆盖率阈值 |

### 3. 安装定时任务与登录提示

```bash
bash scripts/install_cron.sh          # 每日 07:00 / 23:00 headless 巡检
bash scripts/install_login_hook.sh    # SSH 登录时有待确认项会提示（保底通知）
```

注意：WSL2 里 cron 只在 WSL 运行时才触发；公司服务器上使用时把仓库同步过去，
在服务器上重复第 1-3 步即可。

### 4. 手动触发

交互式会话里说 `$loop-engineer distill`，或 headless 执行：

```bash
codex exec --skip-git-repo-check --dangerously-bypass-approvals-and-sandbox < scripts/cron_prompt.txt
```

### 5. 验证安装

```bash
python3 -m pytest tests/              # 全部测试应通过
python3 scripts/scan_sessions.py      # 建立会话索引
python3 scripts/cluster_sessions.py   # 生成候选簇
```

### 工作方式

```text
scan → cluster → extract → validate → review_gate → apply/evolve → notify
```

- 纯新增 / 纯增量的低风险更新自动应用；结构性改动与新 workflow 激活写入
  `digests/inbox.md` 等你确认（登录钩子会自动提示）；
- 通知通道：inbox 保底 + 钉钉（手机）+ Windows Toast（本机 WSL）+ tmux，
  按环境可用性自动选择；
- 产物按名字写入 awesome-skills（`skills/<name>/SKILL.md` + `workflows/<name>.yaml`），
  经 `setup.sh --codex` 激活，每次更新独立 commit 可回滚；
- 密钥只存在 gitignore 的 `config/distill.env`，不会进入 git 历史。

## Install

Install the skill for both Codex and Claude:

```bash
./install.sh
```

The installer reads the skill name from `SKILL.md` frontmatter and installs to:

- Codex: `${CODEX_HOME:-$HOME/.codex}/skills/loop-engineer`
- Claude: `${CLAUDE_HOME:-$HOME/.claude}/skills/loop-engineer`

Codex also receives [`agents/openai.yaml`](./agents/openai.yaml). Restart Codex
after installation so it can discover the skill. Restart Claude Code if the
Claude skills directory did not exist when the session started.

If `grill-me` is not already installed, the installer copies
[`grill-me.md`](./grill-me.md) into each user skill directory as `grill-me`.

You can invoke the skill as `$loop-engineer`.

## What It Produces

A generated workflow should contain:

- one public entry skill
- optional hidden helper skills
- one workflow YAML spec
- explicit inputs, outputs, gates, dependencies, and failure policy

Default layout:

```text
workflow-generator/
├── skills/
│   └── entry-skill/
│       ├── SKILL.md
│       └── hidden/
│           └── helper-skill/
│               └── SKILL.md
└── workflows/
    └── workflow-name.yaml
```

## Core Ideas

- **Structured first**: the durable artifact is a YAML workflow spec, not only a
  natural-language plan.
- **Risk-based clarification**: simple tasks can proceed with conservative
  assumptions; strict tasks require explicit confirmation.
- **Capability inventory**: every required skill, tool, API, credential, or
  generated helper is recorded before execution.
- **Explicit DAG**: every step declares dependencies, inputs, outputs, and
  visibility.
- **Recoverable execution**: retries, rollback, degraded output, blocked states,
  and terminal failures are part of the protocol.
- **Auditable hidden work**: helper steps can be hidden from normal user-facing
  summaries but must still appear in the workflow spec.

## Workflow Lifecycle

LoopEngineer uses a common state machine:

```text
draft -> awaiting_user | ready
ready -> running
running -> validating | rolling_back | degraded | blocked
validating -> succeeded | retrying
retrying -> running
rolling_back -> failed
```

Terminal states are:

- `succeeded`
- `failed`
- `blocked`

Completion is based on acceptance checks, not on agent confidence.

## Request Modes

| Mode | When to use | Behavior |
| --- | --- | --- |
| `simple` | Low-risk request with obvious goal and output | Minimal clarification |
| `guided` | Goal is clear but constraints or acceptance are incomplete | Ask targeted questions |
| `strict` | High-risk, costly, destructive, sensitive, or production-impacting work | Require explicit confirmation |

## Minimal Workflow Spec

```yaml
workflow:
  schema_version: "1.0"
  name: example
  entry_skill: example
  mode: guided
  task_type: deterministic
  visibility: collapsed_by_default
  requirement:
    goal: "Produce the requested artifact"
    output:
      format: "file"
      destination: "workspace"
      consumer: "human"
    constraints: {}
    acceptance:
      checks: ["required artifact exists", "validation passes"]
    assumptions: []
    open_questions: []
  capabilities: []
  inputs: []
  outputs: []
  state_machine: {}
  steps: []
  gates: []
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
    success_when: ["acceptance checks pass"]
    failure_when: ["required capability is unavailable", "retry budget exhausted"]
```

See [`SKILL.md`](./SKILL.md) for the complete protocol.
