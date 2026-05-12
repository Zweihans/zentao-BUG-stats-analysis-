"""用户忽略/确认记录持久化（服务端，不受浏览器/WebView2 影响）"""
import json
import os

BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def _file(project_id: str) -> str:
    return os.path.join(BASE_DIR, f"ignored_{project_id}.json")


def _load(project_id: str) -> dict:
    path = _file(project_id)
    if os.path.exists(path):
        try:
            with open(path, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception:
            pass
    return {}


def _save(project_id: str, data: dict) -> None:
    with open(_file(project_id), 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def get_ignored_unfocused(project_id: str) -> list:
    return _load(project_id).get('unfocused', [])


def add_ignored_unfocused(project_id: str, names: list) -> None:
    data = _load(project_id)
    existing = data.get('unfocused', [])
    for n in names:
        if n not in existing:
            existing.append(n)
    data['unfocused'] = existing
    _save(project_id, data)


def get_ignored_ambiguous(project_id: str) -> list:
    return _load(project_id).get('ambiguous', [])


def add_ignored_ambiguous(project_id: str, pool_names: list) -> None:
    data = _load(project_id)
    existing = data.get('ambiguous', [])
    for n in pool_names:
        if n not in existing:
            existing.append(n)
    data['ambiguous'] = existing
    _save(project_id, data)
