from cluster_sessions import (
    cluster,
    existing_hits_for_members,
    existing_workflows,
    similarity,
    value_score,
)


def _rec(cwd, commands, files, events=100, span=2.0, msgs=5, status="new"):
    return {
        "cwd": cwd,
        "family": cwd.split("/")[-1].split(".")[0],
        "commands": commands,
        "files": files,
        "events": events,
        "span_hours": span,
        "user_message_count": msgs,
        "status": status,
        "session_id": cwd + str(events),
    }


def test_similarity_same_task_high():
    a = _rec("/home/rzyang/Codes/Magnetar", ["pulsar2 build", "git status"], ["config.yaml"])
    b = _rec("/home/rzyang/Codes/Magnetar", ["pulsar2 build", "git log"], ["config.yaml", "model.py"])
    assert similarity(a, b) > 0.5


def test_similarity_different_tasks_low():
    a = _rec("/home/rzyang/Codes/Magnetar", ["pulsar2 build", "docker ps"], ["config.yaml"])
    b = _rec("/home/rzyang/Codes/nand2tetris_verilog", ["iverilog", "vvp"], ["cpu.v"])
    assert similarity(a, b) < 0.3


def test_cluster_separates_groups():
    recs = [
        _rec("/home/rzyang/Codes/Magnetar", ["pulsar2 build", "pytest"], ["a.yaml"]),
        _rec("/home/rzyang/Codes/Magnetar", ["pulsar2 build", "git push"], ["b.yaml"]),
        _rec("/home/rzyang/Codes/nand2tetris_verilog", ["iverilog", "vvp"], ["cpu.v"]),
        _rec("/home/rzyang/Codes/nand2tetris_verilog", ["iverilog", "gtkwave"], ["alu.v"]),
    ]
    groups = cluster(recs, threshold=0.35)
    assert len(groups) == 2
    sizes = sorted(len(g) for g in groups)
    assert sizes == [2, 2]


def test_value_score_grows_with_signals():
    fam_counts = {"Magnetar": 20}
    small = _rec("/home/rzyang/Codes/Magnetar", [], [], events=50, span=0.5, msgs=2)
    big = _rec("/home/rzyang/Codes/Magnetar", [], [], events=5000, span=48.0, msgs=30)
    assert value_score(big, fam_counts) > value_score(small, fam_counts)


def _member(cwd, files, sid="s1"):
    return {
        "cwd": cwd,
        "family": cwd.split("/")[-1].split(".")[0],
        "commands": [],
        "files": files,
        "events": 100,
        "span_hours": 2.0,
        "user_message_count": 5,
        "status": "new",
        "session_id": sid,
    }


def test_existing_workflows_discovers_awesome_and_codex(tmp_path):
    awesome = tmp_path / "awesome-skills"
    demo = awesome / "demo" / "workflows"
    demo.mkdir(parents=True)
    (demo / "demo.yaml").write_text("workflow: {}\n", encoding="utf-8")
    codex = tmp_path / ".codex"
    (codex / "skills" / "magnetar").mkdir(parents=True)
    (codex / "skills" / "magnetar" / "SKILL.md").write_text("---\n", encoding="utf-8")
    (codex / "workflows").mkdir()
    (codex / "workflows" / "refactor.yaml").write_text("workflow: {}\n", encoding="utf-8")

    found = existing_workflows(awesome, codex_home=codex)
    assert found["demo"]["in_awesome"] is True
    assert found["magnetar"]["in_awesome"] is False
    assert found["refactor"]["in_awesome"] is False


def test_existing_hits_marks_project_workflow_skip():
    existing = {"magnetar": {"name": "magnetar", "sources": ["/x/skills/magnetar/SKILL.md"], "in_awesome": False}}
    members = [
        _member("/data/yangrongzhao/Magnetar", ["/data/yangrongzhao/Magnetar/.codex/skills/magnetar/SKILL.md"], "a"),
        _member("/data/yangrongzhao/Magnetar", ["/data/yangrongzhao/Magnetar/workflows/magnetar.yaml"], "b"),
    ]
    hits = existing_hits_for_members(members, existing)
    assert hits and hits[0]["name"] == "magnetar" and hits[0]["in_awesome"] is False


def test_existing_hits_ignores_single_incidental_ref():
    existing = {"magnetar": {"name": "magnetar", "sources": ["/x/skills/magnetar/SKILL.md"], "in_awesome": False}}
    members = [_member("/tmp/other", ["/data/yangrongzhao/Magnetar/workflows/magnetar.yaml"], "a")]
    assert existing_hits_for_members(members, existing) == []


def test_existing_hits_single_strong_ref_counts_as_hit():
    existing = {"magnetar": {"name": "magnetar", "sources": [], "in_awesome": False}}
    members = [
        _member(
            "/data/yangrongzhao/Magnetar",
            [
                "/data/yangrongzhao/Magnetar/.codex/skills/magnetar/SKILL.md",
                "/data/yangrongzhao/Magnetar/workflows/magnetar.yaml",
            ],
            "a",
        )
    ]
    hits = existing_hits_for_members(members, existing)
    assert hits and hits[0]["name"] == "magnetar" and hits[0]["in_awesome"] is False
