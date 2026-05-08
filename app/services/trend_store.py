"""趋势数据存取 — 每日最后导入覆盖"""
import os
import json
import threading

BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
TRENDS_DIR = os.path.join(BASE_DIR, "trends")

# 每项目一把锁，防止并发写入覆盖
_locks: dict[str, threading.Lock] = {}
_locks_lock = threading.Lock()


def _get_lock(project_id: str) -> threading.Lock:
    with _locks_lock:
        if project_id not in _locks:
            _locks[project_id] = threading.Lock()
        return _locks[project_id]


def _trend_file(project_id: str) -> str:
    os.makedirs(TRENDS_DIR, exist_ok=True)
    return os.path.join(TRENDS_DIR, f"{project_id}_trend.json")


def save_trend_record(project_id: str, date: str, analysis_result: dict) -> None:
    """保存/更新指定项目某日的趋势记录（upsert by date）"""
    persons = []
    for p in analysis_result.get('persons', []):
        persons.append({
            'name': p['name'],
            'total': p['total'],
            'S': p.get('S', 0),
            'A': p.get('A', 0),
            'B': p.get('B', 0),
            'C': p.get('C', 0),
            'active': p.get('active', 0),
            'resolved': p.get('resolved', 0),
            'closed': p.get('closed', 0),
        })

    record = {
        'date': date,
        'total_bugs': analysis_result.get('total_bugs', 0),
        'total_persons': analysis_result.get('total_persons', 0),
        'persons': persons,
    }

    filepath = _trend_file(project_id)

    with _get_lock(project_id):
        data = {}
        if os.path.exists(filepath):
            try:
                with open(filepath, 'r', encoding='utf-8') as f:
                    data = json.load(f)
            except Exception:
                pass

        data['project_id'] = project_id
        records = data.get('records', [])

        # upsert by date
        replaced = False
        for i, r in enumerate(records):
            if r.get('date') == date:
                records[i] = record
                replaced = True
                break
        if not replaced:
            records.append(record)

        records.sort(key=lambda r: r['date'])
        data['records'] = records

        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)


def load_trend_data(project_id: str) -> dict | None:
    """加载项目的趋势数据"""
    filepath = _trend_file(project_id)
    if not os.path.exists(filepath):
        return None
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception:
        return None


def delete_trend_data(project_id: str) -> bool:
    """删除项目的趋势数据"""
    filepath = _trend_file(project_id)
    if os.path.exists(filepath):
        os.remove(filepath)
        return True
    return False
