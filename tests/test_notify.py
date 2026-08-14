import json
from pathlib import Path

import notify


def test_applied_workflow_descriptions(tmp_path, monkeypatch):
    applied = tmp_path / "applied.json"
    skill = tmp_path / "skills" / "demo-workflow" / "SKILL.md"
    skill.parent.mkdir(parents=True)
    skill.write_text(
        '---\nname: demo-workflow\ndescription: 把演示任务变成可复用流程\n---\n',
        encoding="utf-8",
    )
    applied.write_text(
        json.dumps(
            {
                "workflows": {
                    "demo-workflow": {
                        "path": str(tmp_path),
                        "kind": "new",
                        "applied_at": "2026-08-14",
                    },
                    "old-workflow": {
                        "path": str(tmp_path),
                        "kind": "new",
                        "applied_at": "2026-08-13",
                    },
                }
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr(notify, "STATE_DIR", tmp_path)
    result = notify.applied_workflow_descriptions("2026-08-14")
    assert result == [("demo-workflow", "把演示任务变成可复用流程")]


def test_workflow_details_text():
    text = notify.workflow_details_text([("demo", "演示流程说明")])
    assert "新增 workflow：" in text
    assert "demo：演示流程说明" in text


def test_dingtalk_sign_has_timestamp_and_sign():
    url = notify.dingtalk_sign("https://oapi.dingtalk.com/robot/send?access_token=x", "SECtest")
    assert "timestamp=" in url
    assert "sign=" in url
    assert url.startswith("https://oapi.dingtalk.com/robot/send?access_token=x&")


def test_inbox_append(tmp_path, monkeypatch):
    monkeypatch.setattr(notify, "DIGEST_DIR", tmp_path)
    inbox = notify.write_inbox("标题", "内容", "digests/2026-08-14.md")
    assert inbox.exists()
    text = inbox.read_text(encoding="utf-8")
    assert "标题" in text and "digests/2026-08-14.md" in text
