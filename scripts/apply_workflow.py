#!/usr/bin/env python3
"""把验证通过的草稿应用到 awesome-skills 仓库并提交。

用法：
  apply_workflow.py --draft state/drafts/<name> --auto        # 新增/纯增量自动
  apply_workflow.py --draft state/drafts/<name> --ask         # 结构性改动需确认
  apply_workflow.py --draft state/drafts/<name> --update --confirm
"""

from __future__ import annotations

import argparse
import json
import re
import shutil
import subprocess
import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import STATE_DIR, cfg_path, ensure_dirs, load_config  # noqa: E402


def _run(cmd: list[str], cwd: Path) -> subprocess.CompletedProcess:
    return subprocess.run(cmd, cwd=cwd, capture_output=True, text=True, timeout=120)


def _diff_kind(old_text: str, new_text: str) -> str:
    old_lines = {l.strip() for l in old_text.splitlines() if l.strip() and not l.strip().startswith("#")}
    new_lines = {l.strip() for l in new_text.splitlines() if l.strip() and not l.strip().startswith("#")}
    removed = old_lines - new_lines
    return "structural" if removed else "additive"


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--draft", required=True)
    ap.add_argument("--auto", action="store_true", help="低风险自动（新增/纯增量）")
    ap.add_argument("--ask", action="store_true", help="结构性改动时等待交互确认")
    ap.add_argument("--update", action="store_true", help="更新已有 workflow")
    ap.add_argument("--confirm", action="store_true", help="强制确认（用于更新已有 workflow 的结构性改动）")
    ap.add_argument("--source-sessions", default="", help="来源会话数，写进 commit/changelog")
    args = ap.parse_args()
    cfg = load_config()
    ensure_dirs()

    draft = Path(args.draft)
    name = draft.name
    skill_md = draft / "skills" / name / "SKILL.md"
    wf_yaml = draft / "workflows" / f"{name}.yaml"
    if not skill_md.exists() or not wf_yaml.exists():
        print(f"error: incomplete draft: {draft}", file=sys.stderr)
        return 1
    awesome = cfg_path(cfg, "AWESOME_SKILLS_DIR", "~/Codes/awesome-skills")
    if not awesome.exists() or not (awesome / ".git").exists():
        print(f"error: awesome-skills repo not found: {awesome}", file=sys.stderr)
        return 1

    target = awesome / name
    existing = target.exists()
    if existing and not args.update:
        print(f"error: {target} already exists; use --update", file=sys.stderr)
        return 1

    new_text = wf_yaml.read_text(encoding="utf-8")
    if existing:
        old_yaml = target / "workflows" / f"{name}.yaml"
        if old_yaml.exists():
            kind = _diff_kind(old_yaml.read_text(encoding="utf-8"), new_text)
            if kind == "structural" and not (args.confirm or args.ask and _confirm(name)):
                print(f"structural change requires confirmation; rerun with --confirm or --ask: {name}")
                return 2
        else:
            kind = "additive"
    else:
        kind = "new"

    if target.exists():
        shutil.rmtree(target)
    shutil.copytree(draft, target)
    setup = awesome / "setup.sh"
    if setup.exists():
        r = _run(["bash", str(setup), "--codex"], awesome)
        if r.returncode != 0:
            print(f"warning: setup.sh failed: {r.stderr[:500]}", file=sys.stderr)

    n = args.source_sessions or str(len(list((draft / "session_summaries.md").read_text(encoding="utf-8").splitlines())))
    action = "add" if kind == "new" else "update"
    msg = f"chore({name}): {action} distilled workflow from {n} sessions"
    r = _run(["git", "add", name], awesome)
    if r.returncode != 0:
        print(f"error: git add failed: {r.stderr[:300]}", file=sys.stderr)
        return 1
    r = _run(["git", "commit", "-m", msg], awesome)
    if r.returncode != 0:
        print(f"warning: git commit failed: {r.stderr[:300]}", file=sys.stderr)

    changelog = target / "CHANGELOG.md"
    entry = f"- {date.today().isoformat()}: {action}（{kind}）from {n} sessions"
    if changelog.exists():
        changelog.write_text(changelog.read_text(encoding="utf-8") + entry + "\n", encoding="utf-8")
    else:
        changelog.write_text(f"# {name} 变更日志\n\n{entry}\n", encoding="utf-8")
    _run(["git", "add", f"{name}/CHANGELOG.md"], awesome)
    _run(["git", "commit", "-m", f"chore({name}): changelog"], awesome)

    applied = STATE_DIR / "applied.json"
    app = json.loads(applied.read_text(encoding="utf-8")) if applied.exists() else {"workflows": {}}
    app["workflows"][name] = {"path": str(target), "kind": kind, "applied_at": date.today().isoformat()}
    applied.write_text(json.dumps(app, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"applied {name} ({kind}) -> {target}")
    return 0


def _confirm(name: str) -> bool:
    print(f"structural change for {name}; type 'y' to confirm: ", end="", flush=True)
    return sys.stdin.readline().strip().lower() in ("y", "yes")


if __name__ == "__main__":
    raise SystemExit(main())
