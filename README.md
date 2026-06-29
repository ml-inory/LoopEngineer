# LoopEngineer

LoopEngineer is an Agent workflow protocol for turning ambiguous user requests
into structured, auditable, and recoverable workflows.

The project is centered on [`SKILL.md`](./SKILL.md). That skill defines how an
agent should clarify requirements, inventory capabilities, design a workflow DAG,
handle retries and rollback, and decide when user approval is required.

## What It Produces

A generated workflow should contain:

- one public entry skill
- optional hidden helper skills
- one workflow YAML spec
- explicit inputs, outputs, gates, dependencies, and failure policy

Default layout:

```text
workflow-generator/
├── README.md
├── skills/
│   └── <entry-skill>/
│       ├── SKILL.md
│       └── hidden/
│           └── <helper-skill>/
│               └── SKILL.md
└── workflows/
    └── <workflow-name>.yaml
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
