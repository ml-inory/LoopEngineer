"""distill 公共工具：配置加载、路径解析、日志。"""

from __future__ import annotations

import os
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parent.parent
CONFIG_FILE = REPO_ROOT / "config" / "distill.env"
STATE_DIR = REPO_ROOT / "state"
DIGEST_DIR = REPO_ROOT / "digests"


def _expand(value: str | None) -> str:
    if not value:
        return ""
    return os.path.expanduser(os.path.expandvars(value.strip()))


def load_config(path: Path | None = None) -> dict[str, str]:
    """读取 config/distill.env（shell 风格 KEY=VALUE），环境变量可覆盖。"""
    cfg: dict[str, str] = {}
    p = path or CONFIG_FILE
    if p.exists():
        for raw in p.read_text(encoding="utf-8").splitlines():
            line = raw.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, _, val = line.partition("=")
            cfg[key.strip()] = _expand(val)
    for key, val in os.environ.items():
        if key in cfg and val:
            cfg[key] = val
    return cfg


def cfg_path(cfg: dict[str, str], key: str, default: str) -> Path:
    return Path(_expand(cfg.get(key) or default))


def cfg_float(cfg: dict[str, str], key: str, default: float) -> float:
    try:
        return float(cfg.get(key) or default)
    except ValueError:
        return default


def cfg_int(cfg: dict[str, str], key: str, default: int) -> int:
    try:
        return int(cfg.get(key) or default)
    except ValueError:
        return default


def ensure_dirs() -> None:
    STATE_DIR.mkdir(parents=True, exist_ok=True)
    DIGEST_DIR.mkdir(parents=True, exist_ok=True)
