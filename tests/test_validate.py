import json

import yaml
from validate_workflow import coverage_for, structural_checks, session_categories


def _write_draft(tmp_path, name, steps=None, states=None):
    draft = tmp_path / name
    (draft / "skills" / name).mkdir(parents=True)
    (draft / "workflows").mkdir(parents=True)
    (draft / "README.md").write_text(
        f"# {name}\n\n测试 workflow。\n\n## 用法\n\n`$loop-engineer {name}`\n\n"
        "## 安装与更新\n\nbash setup.sh --codex\n\n## 维护\n\n走蒸馏 update 流程。\n",
        encoding="utf-8",
    )
    (draft / "skills" / name / "SKILL.md").write_text(
        f"---\nname: {name}\ndescription: test workflow\n---\n\n# {name}\n", encoding="utf-8"
    )
    spec = {
        "workflow": {
            "name": name,
            "entry_skill": name,
            "mode": "guided",
            "task_type": "deterministic",
            "visibility": "collapsed_by_default",
            "steps": steps
            or [
                {"id": "edit", "kind": "agent", "description": "修改代码实现功能", "depends_on": []},
                {"id": "test", "kind": "script", "description": "运行测试验证", "depends_on": ["edit"]},
                {"id": "validate", "kind": "gate", "description": "确认验收通过", "depends_on": ["test"], "pass_when": ["ok"]},
            ],
            "gates": [{"id": "g1", "kind": "validation", "pass_when": ["ok"]}],
            "state_machine": {
                "initial": "draft",
                "states": states
                or [
                    "draft", "awaiting_user", "ready", "running", "validating", "retrying",
                    "rolling_back", "degraded", "blocked", "failed", "succeeded",
                ],
                "terminal": ["blocked", "failed", "succeeded"],
                "transitions": [],
            },
            "failure_policy": {"default_action": "fail", "max_total_attempts": 3},
            "completion": {"success_when": ["ok"]},
            "observability": {"progress_updates": "milestone"},
            "capabilities": [],
            "inputs": [],
            "outputs": [],
        }
    }
    (draft / "workflows" / f"{name}.yaml").write_text(yaml.safe_dump(spec, allow_unicode=True), encoding="utf-8")
    return draft


def test_structural_ok(tmp_path):
    draft = _write_draft(tmp_path, "demo")
    assert structural_checks(draft) == []


def test_structural_missing_states(tmp_path):
    draft = _write_draft(tmp_path, "demo2", states=["draft", "running"])
    errors = structural_checks(draft)
    assert any("state_machine" in e for e in errors)


def test_structural_missing_readme(tmp_path):
    draft = _write_draft(tmp_path, "demo-readme-missing")
    (draft / "README.md").unlink()
    errors = structural_checks(draft)
    assert any("README.md" in e for e in errors)


def test_structural_readme_missing_section(tmp_path):
    draft = _write_draft(tmp_path, "demo-readme-section")
    text = (draft / "README.md").read_text(encoding="utf-8").replace("## 维护", "## 维护缺了")
    (draft / "README.md").write_text(text, encoding="utf-8")
    errors = structural_checks(draft)
    assert any("README.md missing section: ## 维护" in e for e in errors)


def test_coverage_matches_workflow(tmp_path):
    draft = _write_draft(tmp_path, "demo3")
    wf = yaml.safe_load((draft / "workflows" / "demo3.yaml").read_text(encoding="utf-8"))["workflow"]
    rec = {
        "tools": {"exec_command": 5, "apply_patch": 2},
        "commands": ["pytest", "git commit -m x"],
    }
    cats, matched = coverage_for(rec, wf)
    assert "edit" in cats and "test" in cats and "commit" in cats
    assert "edit" in matched and "test" in matched


def test_session_categories():
    rec = {
        "tools": {"exec_command": 3, "apply_patch": 1},
        "commands": ["pytest -q", "git push"],
    }
    cats = session_categories(rec)
    assert {"explore", "edit", "test", "commit"} <= cats
