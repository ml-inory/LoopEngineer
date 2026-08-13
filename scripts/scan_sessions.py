#!/usr/bin/env python3
"""扫描 ~/.codex/sessions，建立/更新会话索引（增量检测 + 信号提取）。

输出：
- state/sessions.json      全量会话索引（幂等，可反复运行）
- state/scan-report.json   本次增量报告（新增/变长/信号汇总）
"""

from __future__ import annotations

import argparse
import json
import re
import shlex
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import STATE_DIR, cfg_int, cfg_path, ensure_dirs, load_config  # noqa: E402


UUID_RE = re.compile(r"[0-9a-fA-F]{8,}")
LONG_RE = re.compile(r"[0-9a-zA-Z_-]{40,}")
FLAG_RE = re.compile(r"^--?[a-zA-Z0-9-]+$")
PATH_RE = re.compile(
    r"(?:/home/[^/\s]+|\.{0,2}/)?(?:[A-Za-z0-9_./-]+/)*"
    r"[A-Za-z0-9_.-]+\.(?:py|sh|yaml|yml|md|json|toml|txt|h|cpp|c|hpp|js|ts|go|rs|axmodel|onnx|pt|npy)"
)
PATCH_FILE_RE = re.compile(r"^\*\*\*\s+(?:Add|Update|Delete|Move to)\s+File:\s+(.+?)\s*$", re.MULTILINE)
SKILL_RE = re.compile(r"\$([a-z][a-z0-9-]+)")


def ts_parse(ts: str) -> datetime:
    return datetime.fromisoformat(ts.replace("Z", "+00:00"))


def canonical_commands(cmd: str) -> set[str]:
    """把一条 shell 命令归一化为一组 2-3 token 的规范命令。"""
    out: set[str] = set()
    for seg in re.split(r"[;&|]+", cmd):
        seg = seg.strip()
        if not seg:
            continue
        try:
            toks = shlex.split(seg)
        except ValueError:
            toks = seg.split()
        if not toks:
            continue
        clean: list[str] = []
        i = 0
        while i < len(toks) and len(clean) < 3:
            t = toks[i]
            if FLAG_RE.match(t):
                clean.append(t)
                i += 2 if i + 1 < len(toks) and not toks[i + 1].startswith("-") else 1
                continue
            if UUID_RE.fullmatch(t) or LONG_RE.fullmatch(t):
                i += 1
                continue
            if re.fullmatch(r"\d+", t) or t in ("2>/dev/null", "1>/dev/null"):
                i += 1
                continue
            clean.append(t)
            i += 1
        if clean:
            out.add(" ".join(clean[:3]))
    return out


def extract_files_from_patch(patch_text: str) -> list[str]:
    return [m.strip() for m in PATCH_FILE_RE.findall(patch_text)]


def extract_files_from_cmd(cmd: str) -> list[str]:
    return [m for m in PATH_RE.findall(cmd)]


def _user_texts(o: dict) -> list[str]:
    texts: list[str] = []
    for c in o.get("content", []):
        if isinstance(c, dict) and c.get("type") == "input_text":
            texts.append(c.get("text") or "")
    return texts


def parse_session(path: Path) -> dict:
    """解析单个会话 jsonl，返回索引记录（不含 delta 状态）。"""
    rec: dict = {
        "session_id": path.name,
        "path": str(path),
        "cwd": "",
        "family": "",
        "originator": "",
        "model_provider": "",
        "first_ts": "",
        "last_ts": "",
        "span_hours": 0.0,
        "events": 0,
        "user_message_count": 0,
        "first_user_message": "",
        "last_user_message": "",
        "commands": [],
        "command_count": 0,
        "files": [],
        "tools": {},
        "skills": [],
    }
    cmd_set: set[str] = set()
    file_set: set[str] = set()
    skill_set: set[str] = set()
    user_msgs: list[str] = []
    ts_list: list[str] = []

    for line in path.open(encoding="utf-8", errors="replace"):
        try:
            o = json.loads(line)
        except json.JSONDecodeError:
            continue
        rec["events"] += 1
        ts = o.get("timestamp")
        if ts:
            ts_list.append(ts)
        otype = o.get("type")
        payload = o.get("payload", {}) if isinstance(o.get("payload"), dict) else {}

        if otype == "session_meta":
            rec["session_id"] = payload.get("session_id") or rec["session_id"]
            rec["cwd"] = payload.get("cwd") or ""
            rec["originator"] = payload.get("originator") or ""
            rec["model_provider"] = payload.get("model_provider") or ""
            continue

        if otype != "response_item":
            continue
        ptype = payload.get("type")
        if ptype == "message":
            role = payload.get("role")
            if role == "user":
                for t in _user_texts(payload):
                    if t and not t.startswith("<environment_context>"):
                        user_msgs.append(t)
                        for s in SKILL_RE.findall(t):
                            skill_set.add(s)
            elif role in ("user", "assistant"):
                for t in _user_texts(payload):
                    for s in SKILL_RE.findall(t):
                        skill_set.add(s)
        elif ptype == "function_call":
            name = payload.get("name") or ""
            rec["tools"][name] = rec["tools"].get(name, 0) + 1
            args = payload.get("arguments") or ""
            try:
                aobj = json.loads(args) if isinstance(args, str) else {}
            except json.JSONDecodeError:
                aobj = {}
            cmd = aobj.get("cmd") or ""
            if name == "exec_command" and cmd:
                cmd_set |= canonical_commands(cmd)
                file_set.update(extract_files_from_cmd(cmd))
        elif ptype == "custom_tool_call":
            name = payload.get("name") or ""
            rec["tools"][name] = rec["tools"].get(name, 0) + 1
            if name == "apply_patch":
                file_set.update(extract_files_from_patch(payload.get("input") or ""))
            elif name in ("spawn_agent", "send_message", "followup_task"):
                skill_set.add(name.replace("_", "-"))

    if ts_list:
        first = ts_parse(ts_list[0])
        last = ts_parse(ts_list[-1])
        rec["first_ts"] = ts_list[0]
        rec["last_ts"] = ts_list[-1]
        rec["span_hours"] = round((last - first).total_seconds() / 3600, 2)

    rec["user_message_count"] = len(user_msgs)
    rec["first_user_message"] = (user_msgs[0][:500] if user_msgs else "")
    rec["last_user_message"] = (user_msgs[-1][:500] if user_msgs else "")
    rec["commands"] = sorted(cmd_set)
    rec["command_count"] = len(cmd_set)
    rec["files"] = sorted(set(file_set))[:200]
    rec["skills"] = sorted(skill_set)
    rec["family"] = family_of(rec["cwd"])
    return rec


def family_of(cwd: str) -> str:
    """cwd 归一化为项目族：home 下的第一层项目目录。"""
    parts = [p for p in cwd.split("/") if p]
    if not parts:
        return ""
    if parts[0].lower() in ("home", "users"):
        parts = parts[2:] if len(parts) > 2 else parts[1:]
    elif parts[0] == "root":
        parts = parts[1:]
    if parts and parts[0].lower() in ("codes", "code", "src", "workspace", "work", "projects", "repos", "repo"):
        parts = parts[1:]
    return parts[0] if parts else ""


def load_prev_index(state_file: Path) -> dict:
    if state_file.exists():
        try:
            data = json.loads(state_file.read_text(encoding="utf-8"))
            return data.get("sessions", {})
        except (json.JSONDecodeError, OSError):
            return {}
    return {}


def build_index(sessions_dir: Path, state_file: Path, days: int | None = None) -> tuple[dict, dict]:
    prev = load_prev_index(state_file)
    all_recs: dict[str, dict] = {}
    report: dict = {"scanned": 0, "new": [], "appended": [], "unchanged": [], "errors": []}
    now = datetime.now(timezone.utc)

    files = sorted(sessions_dir.rglob("*.jsonl"))
    for f in files:
        try:
            rec = parse_session(f)
        except Exception as exc:  # 单文件损坏不阻塞整体扫描
            report["errors"].append({"path": str(f), "error": str(exc)})
            continue
        sid = rec["session_id"]
        report["scanned"] += 1
        prev_rec = prev.get(sid)
        if days and rec["last_ts"]:
            try:
                last = ts_parse(rec["last_ts"])
                if (now - last).total_seconds() > days * 86400:
                    continue
            except ValueError:
                pass
        if prev_rec is None:
            rec["status"] = "new"
            report["new"].append(sid)
        elif int(prev_rec.get("events", 0)) < rec["events"] or prev_rec.get("last_ts", "") < rec["last_ts"]:
            rec["status"] = "appended"
            rec["prev_events"] = int(prev_rec.get("events", 0))
            report["appended"].append(sid)
        else:
            rec["status"] = "unchanged"
            report["unchanged"].append(sid)
        all_recs[sid] = rec

    state_file.parent.mkdir(parents=True, exist_ok=True)
    state_file.write_text(
        json.dumps({"updated_at": now.isoformat(), "sessions": all_recs}, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return all_recs, report


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--sessions-dir", default=None, help="会话目录（默认 config 或 ~/.codex/sessions）")
    ap.add_argument("--state", default=None, help="索引文件路径（默认 state/sessions.json）")
    ap.add_argument("--days", type=int, default=None, help="只处理最近 N 天（缺省=全量/增量）")
    args = ap.parse_args()
    cfg = load_config()
    ensure_dirs()

    sessions_dir = Path(args.sessions_dir) if args.sessions_dir else cfg_path(cfg, "CODEX_SESSIONS_DIR", "~/.codex/sessions")
    state_file = Path(args.state) if args.state else STATE_DIR / "sessions.json"
    if not sessions_dir.exists():
        print(f"error: sessions dir not found: {sessions_dir}", file=sys.stderr)
        return 1

    _, report = build_index(sessions_dir, state_file, days=args.days)
    (STATE_DIR / "scan-report.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(f"scanned={report['scanned']} new={len(report['new'])} appended={len(report['appended'])} unchanged={len(report['unchanged'])} errors={len(report['errors'])}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
