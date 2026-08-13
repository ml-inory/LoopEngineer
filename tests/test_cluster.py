from cluster_sessions import cluster, similarity, value_score


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
