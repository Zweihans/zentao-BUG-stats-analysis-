"""应用配置持久化"""
import os
import json

BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
CONFIG_FILE = os.path.join(BASE_DIR, ".app_config.json")

DEFAULTS = {
    "expiration_hours": 24,
    "schedule_enabled": False,
    "schedule_hour": 9,
}


def _load() -> dict:
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception:
            pass
    return {}


def _save(data: dict) -> None:
    with open(CONFIG_FILE, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def get_config() -> dict:
    data = _load()
    cfg = {}
    for k, v in DEFAULTS.items():
        cfg[k] = data.get(k, v)
    return cfg


def update_config(updates: dict) -> dict:
    data = _load()
    for k in updates:
        if k in DEFAULTS:
            data[k] = updates[k]
    _save(data)
    return get_config()


def get_expiration_hours() -> int:
    return get_config().get('expiration_hours', DEFAULTS['expiration_hours'])
