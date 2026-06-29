---
name: loop-engineer
description: Design auditable, recoverable agent workflows from ambiguous user goals. Use when Codex must turn a request into a structured workflow protocol with requirements, capabilities, DAG steps, gates, retries, rollback, validation, terminal states, generated entry skills, hidden helper skills, or YAML workflow specs.
---

# Loop Engineer

Turn a user's goal into a workflow protocol that another agent or orchestrator can execute with minimal ambiguity. Produce both a concise human-facing summary and a machine-readable workflow specification.

## Core Contract

Generate one public entry skill and any number of hidden helper skills when files are requested. The public entry skill is the user-facing interface. Hidden helper skills are implementation details, but keep them auditable in the workflow spec.

Use this default layout unless the user asks for a different destination:

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

For small workflows, reduce the layout only when the durable artifacts still include:

- one entry `SKILL.md`
- one workflow YAML specification
- all referenced helper skill instructions, unless a helper is explicitly marked as externally provided

## Workflow Design Process

1. Classify the request mode.
2. Build a Requirement Packet.
3. Inventory required capabilities.
4. Design the workflow state machine, steps, gates, failure policy, observability, and completion rules.
5. Generate files when requested.
6. Validate the generated artifacts against the acceptance checks.

Prefer conservative assumptions for low-risk gaps. Ask the user only when missing information materially affects safety, correctness, cost, credentials, production systems, or external side effects.

## Request Modes

Classify every request before designing the workflow.

| Mode | Use when | Default behavior |
| --- | --- | --- |
| `simple` | Goal, inputs, and acceptance are obvious; risk is low | Proceed with minimal clarification |
| `guided` | Goal is clear, but constraints or acceptance are incomplete | Ask targeted questions, then design |
| `strict` | High cost, high risk, destructive operations, security impact, production changes, or legal/financial/medical domain | Restate the Requirement Packet and require explicit confirmation before generation or side effects |

In `simple` mode, proceed if the goal, output format, and at least one acceptance check are clear.

In `guided` mode, ask only for missing fields that affect the workflow design.

In `strict` mode, do not generate or execute side-effecting steps until the user confirms the Requirement Packet and required capabilities.

## Requirement Packet

Construct this packet before workflow generation. If a field is unknown, infer it only when low risk and record the inference in `assumptions`; otherwise ask the user.

```yaml
requirement:
  goal: ""
  output:
    format: ""
    destination: ""
    consumer: "human | system | both"
  constraints:
    time_budget: ""
    cost_budget: ""
    technology: []
    security: []
    human_approval_required: false
  acceptance:
    checks: []
    metrics: []
    required_artifacts: []
  assumptions: []
  open_questions: []
```

## Capability Inventory

Include a capability inventory in every workflow spec. Record existing local skills, generated helper skills, external dependencies, credentials, APIs, tools, and missing capabilities.

```yaml
capabilities:
  - id: ""
    purpose: ""
    source: "existing | install | generate | external | missing"
    skill_path: ""
    permissions: []
    required: true
```

Follow these rules:

- Use existing local skills when discoverable.
- Mark generated helper skills as `generate`.
- Mark unavailable optional capabilities as `missing` and degrade only when acceptable.
- Ask before relying on private systems, credentials, elevated trust, paid actions, publishing, or production changes.
- Do not invent API access, credentials, files, tools, or private services.

## Workflow Spec

Represent every workflow as YAML with this shape:

```yaml
workflow:
  schema_version: "1.0"
  name: ""
  entry_skill: ""
  mode: "simple | guided | strict"
  task_type: "deterministic | exploratory | iterative | hybrid"
  visibility: "collapsed_by_default"
  requirement: {}
  capabilities: []
  inputs: []
  outputs: []
  state_machine: {}
  steps: []
  gates: []
  failure_policy: {}
  observability: {}
  completion: {}
```

### Inputs and Outputs

```yaml
inputs:
  - id: ""
    type: "file | directory | text | url | api | credential | user_decision"
    required: true
    source: "user | environment | generated | external"
    validation: []

outputs:
  - id: ""
    type: "file | directory | text | json | yaml | report | code | decision"
    destination: ""
    required: true
    validation: []
```

### Required State Machine

Every workflow must use these states:

```yaml
state_machine:
  initial: "draft"
  states:
    - draft
    - awaiting_user
    - ready
    - running
    - validating
    - retrying
    - rolling_back
    - degraded
    - blocked
    - failed
    - succeeded
  terminal:
    - blocked
    - failed
    - succeeded
  transitions:
    - from: draft
      to: awaiting_user
      when: "required information or capability source is missing"
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
      to: degraded
      when: "optional capability fails and degraded output is acceptable"
    - from: running
      to: blocked
      when: "required external input, permission, or credential is unavailable"
```

### Steps

Make each step small enough for one focused agent call, one tool call, or one deterministic script.

```yaml
steps:
  - id: ""
    kind: "agent | tool | script | gate | synthesis"
    skill: ""
    description: ""
    depends_on: []
    parallel_group: null
    inputs: []
    outputs: []
    timeout_seconds: null
    retry:
      max_attempts: 0
      retry_on: []
      backoff: "none | fixed | exponential"
    on_failure:
      action: "fail | retry | rollback | ask_user | degrade"
      target_step: null
    visibility: "hidden | summarized | user_visible"
```

Follow these rules:

- Use `depends_on` for all ordering constraints.
- Use `parallel_group` only for independent work.
- Add a gate or synthesis step to join parallel work.
- Do not hide required dependencies in prose.
- Do not create retry loops without `max_attempts`.

## Task Type Rules

Use `deterministic` for known sequential or DAG pipelines. Require explicit dependencies, deterministic validation checks, and rollback or fail behavior for side effects.

Use `exploratory` only when multiple credible approaches need comparison. Create 2 to 4 scout steps, give each scout a distinct hypothesis or evaluation angle, add a synthesis join, record scoring criteria, and capture token, time, or cost limits.

Use `iterative` when quality improves through validation feedback. Include a validation gate, a repair step, `max_attempts`, and a terminal fallback after attempts are exhausted.

Use `hybrid` only when the workflow genuinely combines multiple task types. Mark the relevant behavior through `kind`, `parallel_group`, gates, and retry rules.

## Gates

Make decision points explicit.

```yaml
gates:
  - id: ""
    kind: "requirement | capability | validation | approval | synthesis"
    depends_on: []
    pass_when: []
    fail_when: []
    on_pass: ""
    on_fail: ""
```

Use human approval gates for destructive file operations, production deployments, paid external actions, messages to third parties, publishing, and sensitive credentials.

## Failure Policy

Define failure handling in every workflow.

```yaml
failure_policy:
  default_action: "fail"
  max_total_attempts: 3
  rollback_required_for: []
  ask_user_for: []
  degraded_output_allowed: false
```

Classify failures as:

- `recoverable`: transient tool failure, incomplete output, or validation mismatch
- `blocked`: missing credential, missing file, unavailable private system, or unavailable permission
- `unsafe`: destructive or sensitive action without approval
- `nonrecoverable`: invalid goal, impossible constraints, or exhausted retry budget

Retry only recoverable failures. Roll back side effects when rollback is available and required. Stop at `blocked` instead of guessing credentials, permissions, or private data.

## Observability

Declare what will be recorded.

```yaml
observability:
  progress_updates: "milestone | step | quiet"
  audit_log:
    enabled: true
    include_hidden_steps: true
  artifacts:
    record_intermediate_outputs: true
    retention: "workflow-local"
```

Summarize hidden work in normal user-facing progress. Include hidden details in the audit log and workflow spec.

## Completion

Tie completion to acceptance checks.

```yaml
completion:
  success_when: []
  failure_when: []
  final_response:
    include_artifacts: true
    include_assumptions: true
    include_limitations: true
```

Do not mark a workflow as successful unless acceptance checks pass or the user explicitly accepts degraded output.

## Output Protocol

When designing or generating a workflow, respond in this order:

1. Requirement Packet summary
2. Capability Inventory
3. Workflow Spec
4. Generated file layout, if files are created
5. Open questions, only if they block execution

For simple tasks, keep the user-facing summary brief and include the structured spec as the durable artifact.

## Prohibited Behavior

- Do not rely on hidden chain-of-thought as the workflow definition.
- Do not create parallel steps without an explicit join.
- Do not claim a capability exists unless it is discoverable, generated, or explicitly provided.
- Do not ask for every minor decision when a conservative assumption is low risk and can be recorded.
- Do not continue side-effecting strict workflows without explicit approval.
