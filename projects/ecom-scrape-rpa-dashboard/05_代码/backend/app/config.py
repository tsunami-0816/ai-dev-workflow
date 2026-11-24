"""配置装载与强校验（L1 / T01 / D-01~D-03）。

为什么强校验：配置错误时若仍发起采集，会浪费站点配额并污染观测数据（架构 §3 L1），
所以校验失败直接抛 ConfigError，由 CLI 统一以退出码 2 结束，不发起任何请求。
config_hash = sha1(canonical_json(targets))：targets 变更 → task.version+1（D-03）。
本模块同时承载结构化 jsonl 日志入口（D-79，logs/*.jsonl）。
"""
from __future__ import annotations

import hashlib
import json
import os
from dataclasses import dataclass, field
from datetime import date, datetime
from functools import lru_cache
from pathlib import Path
from zoneinfo import ZoneInfo

import yaml
from dotenv import load_dotenv

BACKEND_ROOT = Path(__file__).resolve().parent.parent
load_dotenv(BACKEND_ROOT / ".env")

VALID_PLATFORMS = {"jd", "tmall", "pdd", "douyin", "mock"}
REAL_PLATFORMS = {"jd", "tmall", "pdd", "douyin"}
TZ = ZoneInfo("Asia/Shanghai")


class ConfigError(Exception):
    """配置非法：进程必须以退出码 2 结束且不发起任何请求（架构 §3 L1）。"""


def now_cn() -> datetime:
    return datetime.now(TZ)


def today_cn() -> date:
    return now_cn().date()


# ---------------------------------------------------------------- 环境配置
def _env_int(key: str, default: int) -> int:
    raw = os.getenv(key, "")
    try:
        return int(raw) if raw.strip() else default
    except ValueError:
        raise ConfigError(f"环境变量 {key} 不是整数: {raw!r}")


@dataclass
class Settings:
    db_host: str
    db_port: int
    db_name: str
    db_root_user: str
    db_root_password: str
    db_rw_user: str
    db_rw_password: str
    db_ro_user: str
    db_ro_password: str
    mock_mode: int          # 1=外部站点走本地 mock_site；0 才允许真实适配器（Mock 红线）
    mock_site_url: str
    api_host: str
    api_port: int
    disable_platforms: set[str]
    disable_rpa: int
    rpa_max_browsers: int
    data_dir: Path
    log_dir: Path
    rw_pool_size: int       # 架构 §1.4：写池 5 / 只读池 10
    ro_pool_size: int

    @property
    def raw_dir(self) -> Path:
        return self.data_dir / "raw"

    @property
    def report_dir(self) -> Path:
        return self.data_dir / "reports"

    @property
    def rpa_dir(self) -> Path:
        return self.data_dir / "rpa_run"


@lru_cache(maxsize=1)
def settings() -> Settings:
    s = Settings(
        db_host=os.getenv("DB_HOST", "127.0.0.1"),
        db_port=_env_int("DB_PORT", 3310),
        db_name=os.getenv("DB_NAME", "ecom_scrape"),
        db_root_user=os.getenv("DB_ROOT_USER", "root"),
        db_root_password=os.getenv("DB_ROOT_PASSWORD", ""),
        db_rw_user=os.getenv("DB_RW_USER", "ecom_rw"),
        db_rw_password=os.getenv("DB_RW_PASSWORD", ""),
        db_ro_user=os.getenv("DB_RO_USER", "ecom_ro"),
        db_ro_password=os.getenv("DB_RO_PASSWORD", ""),
        mock_mode=_env_int("MOCK_MODE", 1),
        mock_site_url=os.getenv("MOCK_SITE_URL", "http://127.0.0.1:5190"),
        api_host=os.getenv("API_HOST", "127.0.0.1"),
        api_port=_env_int("API_PORT", 8094),
        disable_platforms={p.strip() for p in os.getenv("DISABLE_PLATFORMS", "").split(",") if p.strip()},
        disable_rpa=_env_int("DISABLE_RPA", 0),
        rpa_max_browsers=_env_int("RPA_MAX_BROWSERS", 1),
        data_dir=Path(os.getenv("DATA_DIR", str(BACKEND_ROOT / "data"))),
        log_dir=Path(os.getenv("LOG_DIR", str(BACKEND_ROOT / "logs"))),
        rw_pool_size=_env_int("DB_RW_POOL", 5),
        ro_pool_size=_env_int("DB_RO_POOL", 10),
    )
    if not s.db_rw_password or not s.db_ro_password:
        # 口令缺失不静默：记 WARN 由调用方在连接失败时得到可定位的报错（口令只进 .env，不进代码）
        log_event("alert", level="warn", event="DB_PASSWORD_MISSING", hint="复制 .env.example 为 .env 并填写")
    return s


# ---------------------------------------------------------------- targets / sites
@dataclass
class TargetPlatform:
    platform: str
    category: str
    keywords: list[str]
    expect_sku: int          # 目标 SKU 数，<100 时仅 WARN（WARN_SKU_SHORTAGE），不退出


@dataclass
class Targets:
    platforms: list[TargetPlatform]
    freq_cron: str
    raw: dict = field(default_factory=dict)

    @property
    def config_hash(self) -> str:
        # 规范化 JSON 后 sha1：字段顺序/空白差异不产生假版本变更（D-03）
        canon = json.dumps(self.raw, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
        return hashlib.sha1(canon.encode("utf-8")).hexdigest()


@lru_cache(maxsize=1)
def load_targets() -> Targets:
    path = BACKEND_ROOT / "config" / "targets.yaml"
    try:
        raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        raise ConfigError(f"缺少 {path}")
    except yaml.YAMLError as e:
        raise ConfigError(f"targets.yaml 语法错误: {e}")

    errs: list[str] = []
    plats: list[TargetPlatform] = []
    items = raw.get("platforms") or []
    if not items:
        errs.append("targets.platforms 为空")
    for i, it in enumerate(items):
        p = str(it.get("platform", "")).lower()
        if p not in VALID_PLATFORMS:
            errs.append(f"platforms[{i}].platform={p!r} 非法，须 ∈ {sorted(VALID_PLATFORMS)}")
            continue
        kws = it.get("keywords") or []
        if not kws or not all(isinstance(k, str) and k.strip() for k in kws):
            errs.append(f"platforms[{i}].keywords 必须为非空字符串列表")
            continue
        plats.append(
            TargetPlatform(
                platform=p,
                category=str(it.get("category", "default")),
                keywords=kws,
                expect_sku=int(it.get("expect_sku", 0)),
            )
        )
    if errs:
        raise ConfigError("targets.yaml 校验失败: " + "; ".join(errs))

    t = Targets(platforms=plats, freq_cron=str(raw.get("freq_cron", "0 2 * * *")), raw=raw)
    for tp in plats:
        if tp.expect_sku < 100:
            # SKU 不足只 WARN，由 C01 断言兜底（架构 §3 L1），静默会让口径失真
            log_event(
                "collect",
                level="warn",
                event="WARN_SKU_SHORTAGE",
                platform=tp.platform,
                expect_sku=tp.expect_sku,
            )
    return t


@lru_cache(maxsize=1)
def load_sites() -> dict:
    path = BACKEND_ROOT / "config" / "sites.yaml"
    try:
        raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        raise ConfigError(f"缺少 {path}")
    except yaml.YAMLError as e:
        raise ConfigError(f"sites.yaml 语法错误: {e}")
    errs = []
    for name, cfg in (raw.get("sites") or {}).items():
        if name not in VALID_PLATFORMS:
            errs.append(f"sites.{name} 非法平台名")
            continue
        rate = cfg.get("rate") or {}
        qps = float(rate.get("qps", 0))
        if not (0 < qps <= 1):
            # 架构 §3 L1：rate.qps ∈ (0,1]；mock 本地站点也不放宽，保证与真实链路同路径
            errs.append(f"sites.{name}.rate.qps={qps} 越界，须 ∈ (0,1]")
        if int(cfg.get("concurrency", 0)) < 1:
            errs.append(f"sites.{name}.concurrency 须 ≥1")
    if errs:
        raise ConfigError("sites.yaml 校验失败: " + "; ".join(errs))
    return raw


def site_cfg(platform: str) -> dict:
    sites = load_sites()["sites"]
    if platform not in sites:
        raise ConfigError(f"sites.yaml 缺少平台 {platform} 的配置")
    return sites[platform]


def clear_caches() -> None:
    """tests 用：改 env / 临时 yaml 后重载。"""
    settings.cache_clear()
    load_targets.cache_clear()
    load_sites.cache_clear()


# ---------------------------------------------------------------- 结构化日志（D-79）
def log_event(category: str, **fields) -> None:
    """追加一行 jsonl 到 logs/<category>.jsonl（collect/report/rpa/alert/api）。

    只追加不覆盖：排障按 trace_id / run_id 检索；error 字段只存摘要不存堆栈（§6 易漏点）。
    """
    s = settings()
    s.log_dir.mkdir(parents=True, exist_ok=True)
    row = {"ts": now_cn().isoformat(timespec="seconds"), **fields}
    with open(s.log_dir / f"{category}.jsonl", "a", encoding="utf-8") as f:
        f.write(json.dumps(row, ensure_ascii=False, default=str) + "\n")
