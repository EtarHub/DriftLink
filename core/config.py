from datetime import datetime
import json
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
SETTINGS_PATH = BASE_DIR / "settings.json"

DEFAULT_STRATEGIES = [
    {
        "name": "home_cascade_badsum",
        "type": "cascade_fake_disorder",
        "ttl_list": "3,4,5",
        "use_bad_checksum": True,
    },
    {
        "name": "office_clean_multisplit",
        "type": "multisplit",
    },
    {
        "name": "strict_ttl_fake",
        "type": "cascade_fake_disorder",
        "ttl_list": "2,3,4",
        "use_bad_checksum": False,
    },
]


def load_settings() -> dict:
    if SETTINGS_PATH.exists():
        try:
            with open(SETTINGS_PATH, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            print(f"[!] Ошибка чтения settings.json ({e})")
    return {}


def save_settings(data: dict):
    try:
        with open(SETTINGS_PATH, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    except Exception as e:
        print(f"[!] Ошибка сохранения settings.json ({e})")


_cfg = load_settings()

TARGET_DOMAINS: tuple[bytes, ...] = tuple(
    d.encode("ascii") for d in _cfg.get("target_domains", [])
)
STRATEGIES: list[dict] = _cfg.get("strategies", DEFAULT_STRATEGIES)

_raw_favs = _cfg.get("favorites", [])
FAVORITES: list[dict] = [s for s in _raw_favs if isinstance(s, dict)]

FAKE_SNI: bytes = (
    _cfg.get("desync", {}).get("fake_sni", "www.google.com").encode("ascii")
)
BLOCK_QUIC: bool = _cfg.get("desync", {}).get("block_quic", True)
AUTO_SWITCH_TIMEOUT: float = _cfg.get("desync", {}).get(
    "auto_switch_timeout", 2.5
)
VERBOSE_LOG: bool = _cfg.get("logging", {}).get("verbose", True)


def get_favorites() -> list[dict]:
    cfg = load_settings()
    return [s for s in cfg.get("favorites", []) if isinstance(s, dict)]


def add_to_favorites(strategy: dict) -> list[dict]:
    global FAVORITES
    cfg = load_settings()
    favs = [
        s
        for s in cfg.get("favorites", [])
        if isinstance(s, dict) and s.get("name") != strategy.get("name")
    ]
    favs.insert(0, strategy)
    cfg["favorites"] = favs
    FAVORITES = favs
    save_settings(cfg)
    return favs


def remove_from_favorites(name: str):
    global FAVORITES
    cfg = load_settings()
    favs = [
        s
        for s in cfg.get("favorites", [])
        if isinstance(s, dict) and s.get("name") != name
    ]
    cfg["favorites"] = favs
    FAVORITES = favs
    save_settings(cfg)


def get_history() -> list[dict]:
    cfg = load_settings()
    return [h for h in cfg.get("history", []) if isinstance(h, dict)]


def add_to_history(strategy: dict, ping_ms: int):
    cfg = load_settings()
    hist = [h for h in cfg.get("history", []) if isinstance(h, dict)]
    hist.insert(
        0,
        {
            "strategy": strategy,
            "ping_ms": ping_ms,
            "timestamp": datetime.now().strftime("%d.%m %H:%M"),
        },
    )
    cfg["history"] = hist[:30]
    save_settings(cfg)


def clear_history():
    cfg = load_settings()
    cfg["history"] = []
    save_settings(cfg)
