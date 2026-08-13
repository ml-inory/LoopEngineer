#!/usr/bin/env python3
"""蒸馏产物三层验证：结构校验 + holdout 回溯覆盖率。

用法：
  validate_workflow.py --draft state/drafts/<name> [--holdout N] [--threshold 0.8]
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

import yaml

sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import STATE_DIR, cfg_float, ensure_dirs, load_config  # noqa: E402


REQUIRED_STATES = {
    "draft", "awaiting_user", "ready", "running", "validating", "retrying",
    "rolling_back", "degraded", "blocked", "failed", "succeeded",
}
TERMINAL = {"blocked", "failed", "succeeded"}

CATEGORY_KEYWORDS = {
    "explore": ["read", "search", "scan", "explore", "inspect", "查询", "探测", "检查"],
    "edit": ["edit", "write", "patch", "apply", "实现", "修改", "生成"],
    "test": ["test", "check", "lint", "验证", "测试"],
    "fix": ["fix", "repair", "rollback", "retry", "修复", "回退", "重试", "fallback"],
    "commit": ["commit", "push", "提交", "发布", "publish"],
    "ask": ["ask_user", "approval", "approve", "确认", "gate", "stop"],
    "validate": ["validate", "verify", "compare", "simulate", "仿真", "比对", "cosine"],
    "synthesize": ["synthesis", "report", "summary", "汇总", "总结", "package", "打包"],
}


def structural_checks(draft: Path) -> list[str]:
    errors: list[str] = []
    name = draft.name
    skill_md = draft / "skills" / name / "SKILL.md"
    wf_yaml = draft / "workflows" / f"{name}.yaml"
    if not skill_md.exists():
        errors.append(f"missing entry skill: {skill_md}")
    if not wf_yaml.exists():
        errors.append(f"missing workflow yaml: {wf_yaml}")
    if errors:
        return errors

    text = skill_md.read_text(encoding="utf-8")
    m = re.search(r"^name:\s*([a-z0-9-]+)\s*$", text, re.MULTILINE)
    if not m or m.group(1) != name:
        errors.append(f"SKILL.md frontmatter name mismatch: expected {name}")
    if "description:" not in text:
        errors.append("SKILL.md missing description")

    try:
        spec = yaml.safe_load(wf_yaml.read_text(encoding="utf-8"))
    except yaml.YAMLError as exc:
        return errors + [f"YAML parse error: {exc}"]
    wf = spec.get("workflow", spec) if isinstance(spec, dict) else {}
    if not wf:
        return errors + ["workflow root missing"]

    sm = wf.get("state_machine") or {}
    states = set(sm.get("states", []))
    missing = REQUIRED_STATES - states
    if missing:
        errors.append(f"state_machine missing states: {sorted(missing)}")
    if sm.get("initial") not in states:
        errors.append("state_machine.initial not in states")
    term = set(sm.get("terminal", []))
    if not TERMINAL <= term:
        errors.append(f"terminal must include {sorted(TERMINAL)}")

    steps = wf.get("steps") or []
    if not steps:
        errors.append("steps empty")
    seen_ids: set[str] = set()
    for s in steps:
        sid = s.get("id")
        if not sid:
            errors.append("step missing id")
            continue
        if sid in seen_ids:
            errors.append(f"duplicate step id: {sid}")
        seen_ids.add(sid)
        if not s.get("kind"):
            errors.append(f"step {sid} missing kind")
        for dep in s.get("depends_on", []):
            if dep not in seen_ids and dep not in {x.get("id") for x in steps}:
                errors.append(f"step {sid} depends on unknown {dep}")
    for g in wf.get("gates") or []:
        if not g.get("id") or not g.get("pass_when"):
            errors.append(f"gate {g.get('id')} missing id or pass_when")
    for key in ("failure_policy", "completion", "observability", "capabilities", "inputs", "outputs"):
        if key not in wf:
            errors.append(f"missing top-level section: {key}")
    return errors


def session_categories(rec: dict) -> set[str]:
    cats: set[str] = set()
    tools = rec.get("tools", {})
    commands = " ".join(rec.get("commands", []))
    if tools.get("exec_command") or tools.get("search"):
        cats.add("explore")
    if tools.get("apply_patch"):
        cats.add("edit")
    if re.search(r"test|lint|check|pytest|mypy|ruff|validate|验证", commands):
        cats.add("test")
    if re.search(r"fix|repair|修复|回退|rollback", commands):
        cats.add("fix")
    if re.search(r"git (commit|push)", commands):
        cats.add("commit")
    if tools.get("request_user_input"):
        cats.add("ask")
    return cats


def coverage_for(rec: dict, wf: dict) -> tuple[set[str], set[str]]:
    cats = session_categories(rec)
    haystack = " ".join(
        [str(s.get("kind", "")) + " " + str(s.get("description", "")) for s in wf.get("steps", [])]
        + [str(g.get("kind", "")) + " " + str(g.get("pass_when", [])) for g in wf.get("gates", [])]
    ).lower()
    matched: set[str] = set()
    for cat in cats:
        if any(kw.lower() in haystack for kw in CATEGORY_KEYWORDS[cat]):
            matched.add(cat)
    return cats, matched


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--draft", required=True, help="草稿目录 state/drafts/<name>")
    ap.add_argument("--holdout", type=int, default=2, help="留出 N 个会话做回溯（默认 2）")
    ap.add_argument("--threshold", type=float, default=None, help="覆盖率阈值（默认 config 0.8）")
    args = ap.parse_args()
    cfg = load_config()
    ensure_dirs()
    draft = Path(args.draft)
    if not draft.exists():
        print(f"error: draft not found: {draft}", file=sys.stderr)
        return 1

    errors = structural_checks(draft)
    if errors:
        report = {"passed": False, "errors": errors}
        (draft / "validation.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
        print("FAIL structural:\n - " + "\n - ".join(errors))
        return 1

    threshold = args.threshold if args.threshold is not None else cfg_float(cfg, "COVERAGE_THRESHOLD", 0.8)
    name = draft.name
    wf = yaml.safe_load((draft / "workflows" / f"{name}.yaml").read_text(encoding="utf-8"))
    wf = wf.get("workflow", wf)

    sessions_file = STATE_DIR / "sessions.json"
    cov_ok = True
    per_session: list[dict] = []
    if sessions_file.exists() and args.holdout > 0:
        sessions = json.loads(sessions_file.read_text(encoding="utf-8")).get("sessions", {})
        recs = list(sessions.values())
        holdout = recs[: args.holdout]
        for rec in holdout:
            cats, matched = coverage_for(rec, wf)
            cov = (len(matched) / len(cats)) if cats else 1.0
            per_session.append(
                {"session": rec["session_id"], "categories": sorted(cats), "matched": sorted(matched), "coverage": round(cov, 2)}
            )
            if cov < threshold:
                cov_ok = False

    report = {"passed": cov_ok, "structural_errors": [], "threshold": threshold, "coverage": per_session}
    (draft / "validation.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    if not cov_ok:
        print(f"FAIL coverage < {threshold}: {per_session}")
        return 1
    print(f"PASS structural + coverage (holdout={len(per_session)})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
