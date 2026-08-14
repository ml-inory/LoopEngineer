#!/usr/bin/env python3
"""基于动作指纹的会话聚类：命令/文件 Jaccard + cwd 家族 + 价值评分。

输出：
- state/candidates.json      候选簇 + 高价值单会话 + 已有 workflow 清单
- state/cluster-summaries.md 供 LLM 阅读的紧凑摘要（token 高效）
"""

from __future__ import annotations

import argparse
import json
import math
import os
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import STATE_DIR, cfg_float, cfg_int, cfg_path, ensure_dirs, load_config  # noqa: E402


def jaccard(a: list[str], b: list[str]) -> float:
    sa, sb = set(a), set(b)
    if not sa or not sb:
        return 0.0
    return len(sa & sb) / len(sa | sb)


def similarity(a: dict, b: dict) -> float:
    cmd = jaccard(a.get("commands", []), b.get("commands", []))
    files = jaccard(a.get("files", [])[:80], b.get("files", [])[:80])
    fam = 1.0 if a.get("family") and a.get("family") == b.get("family") else 0.0
    same_cwd = 1.0 if a.get("cwd") and a.get("cwd") == b.get("cwd") else 0.0
    score = 0.55 * cmd + 0.30 * files + 0.15 * fam + 0.10 * same_cwd
    return min(score, 1.0)


class UnionFind:
    def __init__(self, n: int):
        self.p = list(range(n))

    def find(self, x: int) -> int:
        while self.p[x] != x:
            self.p[x] = self.p[self.p[x]]
            x = self.p[x]
        return x

    def union(self, x: int, y: int) -> None:
        rx, ry = self.find(x), self.find(y)
        if rx != ry:
            self.p[ry] = rx


def cluster(recs: list[dict], threshold: float, max_cluster: int = 12) -> list[list[int]]:
    n = len(recs)
    uf = UnionFind(n)
    for i in range(n):
        for j in range(i + 1, n):
            sim = similarity(recs[i], recs[j])
            if sim < threshold:
                continue
            size = sum(1 for k in range(n) if uf.find(k) == uf.find(i) or uf.find(k) == uf.find(j))
            if size > max_cluster and sim < threshold + 0.15:
                continue
            uf.union(i, j)
    groups: dict[int, list[int]] = {}
    for i in range(n):
        groups.setdefault(uf.find(i), []).append(i)
    return [g for g in groups.values() if len(g) > 1]


def value_score(rec: dict, family_count: dict[str, int]) -> float:
    events = float(rec.get("events", 0))
    span = float(rec.get("span_hours", 0.0))
    msgs = float(rec.get("user_message_count", 0))
    fam = rec.get("family", "") or ""
    density = float(family_count.get(fam, 1))
    s_events = min(math.log10(events + 1) / 4.0, 1.0)
    s_span = min(math.log10(span + 1) / 2.0, 1.0)
    s_msgs = min(msgs / 20.0, 1.0) * 0.5
    s_density = min(math.log10(density + 1) / math.log10(21.0), 1.0)
    s_growth = 0.2 if rec.get("status") in ("new", "appended") else 0.0
    score = 100.0 * (0.35 * s_events + 0.30 * s_span + 0.15 * s_msgs + 0.15 * s_density + 0.05 * s_growth)
    return round(score, 1)


def _codex_home() -> Path:
    env = os.environ.get("CODEX_HOME")
    return Path(env).expanduser() if env else Path(os.path.expanduser("~/.codex"))


def existing_workflows(awesome_dir: Path, codex_home: Path | None = None) -> dict[str, dict]:
    """收集已有 workflow：awesome-skills 产物 + Codex/Claude 已安装 skill 与 workflow。"""
    result: dict[str, dict] = {}

    def add(name: str, source: str, in_awesome: bool) -> None:
        name = name.strip()
        if not name:
            return
        entry = result.setdefault(name, {"name": name, "sources": [], "in_awesome": False})
        if source not in entry["sources"]:
            entry["sources"].append(source)
        if in_awesome:
            entry["in_awesome"] = True

    if awesome_dir.exists():
        for wf in sorted(awesome_dir.glob("*/workflows/*.y*ml")):
            add(wf.parent.parent.name, str(wf), True)

    codex = codex_home or _codex_home()
    for skill_dir in sorted((codex / "skills").glob("*")):
        if (skill_dir / "SKILL.md").exists():
            add(skill_dir.name, str(skill_dir / "SKILL.md"), False)
    for wf in sorted((codex / "workflows").glob("*.y*ml")):
        add(wf.stem, str(wf), False)

    claude = Path(os.path.expanduser("~/.claude"))
    for skill_dir in sorted((claude / "skills").glob("*")):
        if (skill_dir / "SKILL.md").exists():
            add(skill_dir.name, str(skill_dir / "SKILL.md"), False)

    return dict(sorted(result.items()))


def workflow_refs(paths: list[str]) -> list[tuple[str, str]]:
    """从会话文件路径里反推被使用的 workflow/skill 名称。"""
    refs: list[tuple[str, str]] = []
    for raw in paths:
        p = raw.replace("\\", "/")
        m = re.search(r"(?:^|/)workflows/([^/]+?)\.ya?ml(?:\b|$)", p)
        if m:
            refs.append((m.group(1), raw))
            continue
        m = re.search(r"(?:^|/)workflows/([^/]+?)-summary\.md(?:\b|$)", p)
        if m:
            refs.append((m.group(1), raw))
            continue
        m = re.search(r"(?:^|/)(?:\.codex/)?skills/([^/]+?)/SKILL\.md(?:\b|$)", p)
        if m:
            refs.append((m.group(1), raw))
    return refs


def existing_hits_for_members(members: list[dict], existing: dict[str, dict]) -> list[dict]:
    """返回会话确实引用过的已有 workflow；至少 2 个会话引用或单个会话强引用才算命中。"""
    counts: dict[str, int] = {}
    sources: dict[str, list[str]] = {}
    strong: set[str] = set()
    for member in members:
        refs = workflow_refs(member.get("files", []))
        names = {name for name, _ in refs}
        for name in names:
            counts[name] = counts.get(name, 0) + 1
            member_sources = {path for n, path in refs if n == name}
            sources.setdefault(name, []).extend(member_sources)
            if len(member_sources) >= 2:
                strong.add(name)
    threshold = min(2, len(members)) if members else 1
    hits: list[dict] = []
    for name, cnt in counts.items():
        if cnt < threshold and name not in strong:
            continue
        if len(members) == 1 and len(set(sources[name])) < 2:
            continue
        known = existing.get(name, {"name": name, "sources": [], "in_awesome": False})
        all_sources = sorted(set(sources[name] + known.get("sources", [])))
        hits.append(
            {
                "name": name,
                "sources": all_sources,
                "in_awesome": bool(known.get("in_awesome")),
            }
        )
    return sorted(hits, key=lambda h: h["name"])


def build_candidates(sessions_file: Path, awesome_dir: Path, min_sessions: int, threshold: float, high_score: float) -> dict:
    data = json.loads(sessions_file.read_text(encoding="utf-8"))
    recs = list(data.get("sessions", {}).values())
    if not recs:
        return {"clusters": [], "high_value_singles": [], "existing_workflows": [], "sessions_total": 0}
    family_count: dict[str, int] = {}
    for r in recs:
        f = r.get("family") or ""
        family_count[f] = family_count.get(f, 0) + 1

    existing = existing_workflows(awesome_dir)
    groups = cluster(recs, threshold)
    clusters: list[dict] = []
    for g in groups:
        members = [recs[i] for i in g]
        top_cmds = _top(members, "commands", 10)
        top_files = _top(members, "files", 10)
        fams = sorted({m.get("family") for m in members if m.get("family")})
        scores = [value_score(m, family_count) for m in members]
        hits = existing_hits_for_members(members, existing)
        suggestion = "review"
        if hits:
            suggestion = "update" if any(h["in_awesome"] for h in hits) else "skip"
        clusters.append(
            {
                "cluster_id": f"c{len(clusters) + 1}",
                "session_ids": [m["session_id"] for m in members],
                "count": len(members),
                "families": fams,
                "top_commands": top_cmds,
                "top_files": top_files,
                "member_scores": scores,
                "value_score": round(max(scores) + 0.15 * (sum(scores) / len(scores)), 1),
                "existing_hits": hits,
                "suggestion": suggestion,
            }
        )

    used: set[str] = set()
    for c in clusters:
        used.update(c["session_ids"])
    singles = []
    for r in recs:
        if r["session_id"] in used:
            continue
        sc = value_score(r, family_count)
        if sc >= high_score:
            hits = existing_hits_for_members([r], existing)
            suggestion = "update" if hits and any(h["in_awesome"] for h in hits) else "skip" if hits else "review"
            singles.append(
                {
                    "session_id": r["session_id"],
                    "family": r.get("family"),
                    "value_score": sc,
                    "first_user_message": (r.get("first_user_message") or "")[:300],
                    "existing_hits": hits,
                    "suggestion": suggestion,
                }
            )
    singles.sort(key=lambda s: -s["value_score"])

    return {
        "clusters": clusters,
        "high_value_singles": singles,
        "existing_workflows": list(existing.values()),
        "sessions_total": len(recs),
    }


def _top(members: list[dict], field: str, n: int) -> list[dict]:
    cnt: dict[str, int] = {}
    for m in members:
        for v in m.get(field, []):
            cnt[v] = cnt.get(v, 0) + 1
    return [{"value": k, "hits": v} for k, v in sorted(cnt.items(), key=lambda kv: -kv[1])[:n]]


def write_summaries(candidates: dict, sessions: dict[str, dict], out: Path) -> None:
    lines = ["# 会话蒸馏候选摘要（供 extract 阶段读取，勿读原始会话）", ""]
    for c in candidates["clusters"]:
        lines.append(f"## {c['cluster_id']}（{c['count']} 会话, value={c['value_score']}, family={','.join(c['families'])}）")
        if c.get("existing_hits"):
            lines.append(
                "命中已有 workflow: "
                + ", ".join(
                    f"{h['name']}(in_awesome={h['in_awesome']}, 建议 {'update' if h['in_awesome'] else 'skip'})"
                    for h in c["existing_hits"]
                )
            )
        lines.append("顶层命令: " + ", ".join(f"{t['value']}×{t['hits']}" for t in c["top_commands"][:6]))
        lines.append("相关文件: " + ", ".join(f"{t['value']}×{t['hits']}" for t in c["top_files"][:6]))
        lines.append("")
        for sid in c["session_ids"]:
            s = sessions.get(sid, {})
            lines.append(f"- {sid[:20]}… 首条: {(s.get('first_user_message') or '')[:180]}")
        lines.append("")
    if candidates["high_value_singles"]:
        lines.append("## 高价值单会话")
        for s in candidates["high_value_singles"]:
            if s.get("existing_hits"):
                lines.append(f"- 命中已有 workflow: {', '.join(h['name'] for h in s['existing_hits'])}")
            lines.append(f"- {s['session_id'][:20]}… value={s['value_score']} {s['first_user_message'][:160]}")
    out.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--sessions", default=None, help="state/sessions.json 路径")
    ap.add_argument("--out", default=None, help="candidates.json 输出路径")
    args = ap.parse_args()
    cfg = load_config()
    ensure_dirs()
    sessions_file = Path(args.sessions) if args.sessions else STATE_DIR / "sessions.json"
    if not sessions_file.exists():
        print(f"error: {sessions_file} not found; run scan_sessions.py first", file=sys.stderr)
        return 1
    awesome_dir = cfg_path(cfg, "AWESOME_SKILLS_DIR", "~/Codes/awesome-skills")
    candidates = build_candidates(
        sessions_file,
        awesome_dir,
        min_sessions=cfg_int(cfg, "CLUSTER_MIN_SESSIONS", 2),
        threshold=cfg_float(cfg, "CLUSTER_THRESHOLD", 0.35),
        high_score=cfg_float(cfg, "HIGH_VALUE_SINGLE_SCORE", 55),
    )
    out = Path(args.out) if args.out else STATE_DIR / "candidates.json"
    out.write_text(json.dumps(candidates, ensure_ascii=False, indent=2), encoding="utf-8")
    sessions = json.loads(sessions_file.read_text(encoding="utf-8")).get("sessions", {})
    write_summaries(candidates, sessions, STATE_DIR / "cluster-summaries.md")
    print(f"clusters={len(candidates['clusters'])} singles={len(candidates['high_value_singles'])} workflows_existing={len(candidates['existing_workflows'])}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
