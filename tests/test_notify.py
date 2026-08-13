import notify


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
