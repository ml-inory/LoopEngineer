import subprocess
from pathlib import Path

import pytest

import apply_workflow


def test_ensure_repo_clones_when_missing(tmp_path, monkeypatch):
    target = tmp_path / "awesome-skills"
    calls = []

    def fake_run(cmd, capture_output, text, timeout, env):
        calls.append(cmd)
        (target / ".git").mkdir(parents=True)
        return subprocess.CompletedProcess(cmd, 0, "", "")

    monkeypatch.setattr(apply_workflow.subprocess, "run", fake_run)
    cfg = {"AWESOME_SKILLS_DIR": str(target), "AWESOME_SKILLS_REPO": "git@github.com:ml-inory/awesome-skills.git"}
    result = apply_workflow.ensure_awesome_repo(cfg)
    assert result == target
    assert calls[0][:2] == ["git", "clone"]


def test_ensure_repo_errors_on_non_git_dir(tmp_path):
    target = tmp_path / "awesome-skills"
    target.mkdir()
    cfg = {"AWESOME_SKILLS_DIR": str(target), "AWESOME_SKILLS_REPO": "git@example.com:x.git"}
    with pytest.raises(RuntimeError, match="不是 git 仓库"):
        apply_workflow.ensure_awesome_repo(cfg)


def test_ensure_repo_errors_without_repo_url(tmp_path, monkeypatch):
    target = tmp_path / "awesome-skills"
    cfg = {"AWESOME_SKILLS_DIR": str(target)}
    with pytest.raises(RuntimeError, match="AWESOME_SKILLS_REPO"):
        apply_workflow.ensure_awesome_repo(cfg)
