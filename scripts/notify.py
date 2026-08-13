#!/usr/bin/env python3
"""多通道通知：inbox（保底）+ 钉钉 webhook + Windows Toast + tmux。

用法：notify.py --title "..." --message "..." [--digest digests/2026-08-14.md] [--dry-run]
"""

from __future__ import annotations

import argparse
import base64
import hashlib
import hmac
import json
import os
import shutil
import subprocess
import sys
import time
import urllib.parse
import urllib.request
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import DIGEST_DIR, REPO_ROOT, ensure_dirs, load_config  # noqa: E402


def dingtalk_sign(webhook: str, secret: str) -> str:
    ts = str(round(time.time() * 1000))
    string_to_sign = f"{ts}\n{secret}"
    digest = hmac.new(secret.encode(), string_to_sign.encode(), hashlib.sha256).digest()
    sign = urllib.parse.quote_plus(base64.b64encode(digest))
    sep = "&" if "?" in webhook else "?"
    return f"{webhook}{sep}timestamp={ts}&sign={sign}"


def send_dingtalk(webhook: str, secret: str, text: str, dry_run: bool = False) -> bool:
    url = dingtalk_sign(webhook, secret)
    body = json.dumps({"msgtype": "text", "text": {"content": text}}).encode("utf-8")
    if dry_run:
        print(f"[dry-run] dingtalk -> {text[:80]}")
        return True
    req = urllib.request.Request(url, data=body, headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            result = json.loads(resp.read().decode("utf-8"))
        return bool(result.get("errcode") == 0)
    except Exception as exc:
        print(f"[warn] dingtalk failed: {exc}", file=sys.stderr)
        return False


def write_inbox(title: str, message: str, digest: str | None, dry_run: bool = False) -> Path:
    ensure_dirs()
    inbox = DIGEST_DIR / "inbox.md"
    stamp = datetime.now().strftime("%Y-%m-%d %H:%M")
    line = f"- [{stamp}] {title}: {message}"
    if digest:
        line += f"（{digest}）"
    if dry_run:
        print(f"[dry-run] inbox += {line}")
        return inbox
    with inbox.open("a", encoding="utf-8") as fh:
        fh.write(line + "\n")
    return inbox


def send_toast(title: str, message: str, dry_run: bool = False) -> bool:
    ps = shutil.which("powershell.exe")
    script = REPO_ROOT / "scripts" / "toast.ps1"
    if not ps or not script.exists():
        return None  # 本机无 Windows 通道，跳过
    import tempfile

    with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False, encoding="utf-8") as fh:
        json.dump({"title": title, "message": message}, fh, ensure_ascii=False)
        cfg_path = fh.name
    try:
        if dry_run:
            print(f"[dry-run] toast via {ps}")
            return True
        subprocess.run(
            [ps, "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", str(script), "-ConfigPath", cfg_path],
            capture_output=True,
            timeout=20,
        )
        return True
    except Exception as exc:
        print(f"[warn] toast failed: {exc}", file=sys.stderr)
        return False
    finally:
        try:
            os.unlink(cfg_path)
        except OSError:
            pass


def send_tmux(message: str, dry_run: bool = False) -> bool:
    if not os.environ.get("TMUX") or not shutil.which("tmux"):
        return None  # 不在 tmux 会话内，跳过
    try:
        if dry_run:
            print(f"[dry-run] tmux display-message {message[:60]}")
            return True
        subprocess.run(["tmux", "display-message", message], timeout=5)
        return True
    except Exception as exc:
        print(f"[warn] tmux notify failed: {exc}", file=sys.stderr)
        return False


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--title", required=True)
    ap.add_argument("--message", required=True)
    ap.add_argument("--digest", default=None, help="相对 repo 的 digest 路径，便于 inbox 引用")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--channels", nargs="*", default=["inbox", "dingtalk", "toast", "tmux"])
    args = ap.parse_args()
    cfg = load_config()

    results: list[bool] = []
    if "inbox" in args.channels:
        write_inbox(args.title, args.message, args.digest, args.dry_run)
    if "dingtalk" in args.channels and cfg.get("DINGTALK_WEBHOOK") and cfg.get("DINGTALK_SECRET"):
        results.append(send_dingtalk(cfg["DINGTALK_WEBHOOK"], cfg["DINGTALK_SECRET"], f"{args.title}\n{args.message}", args.dry_run))
    if "toast" in args.channels:
        r = send_toast(args.title, args.message, args.dry_run)
        if r is not None:
            results.append(r)
    if "tmux" in args.channels:
        r = send_tmux(f"{args.title}: {args.message[:80]}", args.dry_run)
        if r is not None:
            results.append(r)
    return 0 if all(results) else 1


if __name__ == "__main__":
    raise SystemExit(main())
