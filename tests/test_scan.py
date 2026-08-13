import json

from scan_sessions import build_index, parse_session


def _write(tmp_path, name, lines):
    p = tmp_path / name
    p.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return p


def test_parse_session(tmp_path):
    p = _write(
        tmp_path,
        "a.jsonl",
        [
            '{"timestamp":"2026-08-01T02:00:00Z","type":"session_meta","payload":{"session_id":"a","cwd":"/home/rzyang/Codes/Magnetar","originator":"codex-tui"}}',
            '{"timestamp":"2026-08-01T02:00:01Z","type":"response_item","payload":{"type":"function_call","name":"exec_command","arguments":"{\\"cmd\\": \\"git status\\"}"}}',
            '{"timestamp":"2026-08-01T03:00:00Z","type":"response_item","payload":{"type":"message","role":"user","content":[{"type":"input_text","text":"$loop-engineer 帮我蒸馏"}]}}',
        ],
    )
    rec = parse_session(p)
    assert rec["session_id"] == "a"
    assert rec["family"] == "Magnetar"
    assert rec["span_hours"] == 1.0
    assert "git status" in rec["commands"]
    assert "$loop-engineer 帮我蒸馏".find("loop-engineer") != -1
    assert "loop-engineer" in rec["skills"]
    assert rec["user_message_count"] == 1


def test_build_index_delta(tmp_path):
    sessions = tmp_path / "sessions"
    sessions.mkdir()
    state = tmp_path / "state.json"
    lines = [
        '{"timestamp":"2026-08-02T00:00:00Z","type":"session_meta","payload":{"session_id":"s1","cwd":"/home/rzyang/Codes/AxTTS"}}',
        '{"timestamp":"2026-08-02T00:00:01Z","type":"response_item","payload":{"type":"message","role":"user","content":[{"type":"input_text","text":"hi"}]}}',
    ]
    (sessions / "s1.jsonl").write_text("\n".join(lines) + "\n", encoding="utf-8")

    recs, report = build_index(sessions, state)
    assert report["new"] == ["s1"]
    assert recs["s1"]["status"] == "new"

    # 追加事件后再次扫描 → appended
    lines.append('{"timestamp":"2026-08-03T00:00:00Z","type":"response_item","payload":{"type":"function_call","name":"exec_command","arguments":"{\\"cmd\\": \\"pytest\\"}"}}')
    (sessions / "s1.jsonl").write_text("\n".join(lines) + "\n", encoding="utf-8")
    recs, report = build_index(sessions, state)
    assert report["appended"] == ["s1"]
    assert recs["s1"]["status"] == "appended"
    assert "pytest" in recs["s1"]["commands"]


def test_family_normalization():
    from scan_sessions import family_of

    assert family_of("/home/rzyang/Codes/Magnetar") == "Magnetar"
    assert family_of("/home/rzyang/Codes/VoiceAssistant/ax_tts_api") == "VoiceAssistant"
    assert family_of("/home/rzyang/moon-bridge") == "moon-bridge"
