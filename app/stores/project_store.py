"""项目配置读写"""
import json
import os

BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
CONFIG_FILE = os.path.join(BASE_DIR, "import_projects.json")


def load_projects() -> list:
    if not os.path.exists(CONFIG_FILE):
        return []
    try:
        with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
            data = json.load(f)
    except Exception:
        return []

    if isinstance(data, dict) and 'projects' in data:
        projects = data['projects']
    elif isinstance(data, list):
        projects = data
    else:
        return []

    result = []
    for p in projects:
        if isinstance(p, dict):
            result.append({
                'id': str(p.get('id', p.get('name', ''))),
                'name': p.get('name', ''),
                'url': p.get('url', ''),
                'focus': p.get('focus', False),
            })
    return result


def save_projects(projects: list) -> None:
    data = {'projects': []}
    for p in projects:
        data['projects'].append({
            'name': p.get('name', ''),
            'url': p.get('url', ''),
            'focus': p.get('focus', False),
        })
    # 保留 id 如果有的话
    for i, p in enumerate(projects):
        if 'id' in p:
            data['projects'][i]['id'] = p['id']

    with open(CONFIG_FILE, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def find_project(project_id: str) -> dict | None:
    projects = load_projects()
    for p in projects:
        if p['id'] == project_id or p['name'] == project_id:
            return p
    return None
