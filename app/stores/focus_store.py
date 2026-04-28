"""关注人员读写"""
import json
import os
import re

BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
DEFAULT_FILE = os.path.join(BASE_DIR, "focus_list.json")


def load_focus_list(project_id: str = None) -> list:
    """加载关注人员列表"""
    persons = []

    # 先尝试项目专属列表
    if project_id:
        list_file = os.path.join(BASE_DIR, f"{project_id}list.json")
        if os.path.exists(list_file):
            try:
                with open(list_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                if isinstance(data, list):
                    persons = data
                elif isinstance(data, dict):
                    persons = data.get('focus_persons', [])
            except Exception:
                pass
        if persons:
            return persons

    # 默认列表
    if os.path.exists(DEFAULT_FILE):
        try:
            with open(DEFAULT_FILE, 'r', encoding='utf-8') as f:
                data = json.load(f)
            if isinstance(data, list):
                persons = data
            elif isinstance(data, dict):
                persons = data.get('focus_persons', [])
        except Exception:
            pass

    return persons


def save_focus_list(persons: list, project_id: str = None) -> None:
    """保存关注人员列表"""
    if project_id:
        list_file = os.path.join(BASE_DIR, f"{project_id}list.json")
    else:
        list_file = DEFAULT_FILE

    with open(list_file, 'w', encoding='utf-8') as f:
        json.dump(persons, f, ensure_ascii=False, indent=2)


def extract_project_id(filename: str) -> str | None:
    """从文件名提取项目标识，如 C62X-E19_20260424.xlsx → C62X"""
    basename = os.path.basename(filename)
    patterns = [r'B\d+X?-E\d+', r'C\d+X', r'\w+']
    for pattern in patterns:
        match = re.search(pattern, basename, re.IGNORECASE)
        if match and len(match.group(0)) >= 4:
            return match.group(0).upper()
    return None


def is_focused(person_name: str, focus_list: list) -> bool:
    """检查人员是否在关注列表中（支持部分匹配）"""
    if not focus_list:
        return False
    name_lower = person_name.lower()
    for f in focus_list:
        f_lower = f.lower()
        if name_lower == f_lower or name_lower in f_lower or f_lower in name_lower:
            return True
    return False
