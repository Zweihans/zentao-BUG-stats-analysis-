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
    """检查人员是否在关注列表中（全名精确匹配，忽略大小写）"""
    if not focus_list:
        return False
    name_lower = person_name.lower()
    for f in focus_list:
        if name_lower == f.lower():
            return True
    return False


# ========== 全局应关注人员池 ==========
POOL_FILE = os.path.join(BASE_DIR, "focus_pool.json")


def load_focus_pool() -> list:
    """加载全局应关注人员姓名列表"""
    if os.path.exists(POOL_FILE):
        try:
            with open(POOL_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception:
            pass
    return []


def save_focus_pool(names: list) -> None:
    """保存全局应关注人员姓名列表"""
    with open(POOL_FILE, 'w', encoding='utf-8') as f:
        json.dump(names, f, ensure_ascii=False, indent=2)


def merge_into_pool(new_names: list) -> int:
    """合并新姓名到池中，返回新增数量"""
    existing = set(load_focus_pool())
    before = len(existing)
    existing.update(new_names)
    after = len(existing)
    if after > before:
        save_focus_pool(sorted(existing))
    return after - before


def extract_chinese_names(full_name: str) -> list:
    """从禅道全名中提取所有中文姓名片段
    T:田春艳(#tianchunyan) → ['田春艳']
    A:艾博连-孙超(#abl-sunchao) → ['艾博连', '孙超']
    李涛2 → ['李涛']
    """
    import re
    # 去掉末尾数字
    name = re.sub(r'\d+$', '', full_name)
    matches = re.findall(r'[一-鿿]{2,4}', name)
    return matches if matches else [full_name]


def _match_pool_name(zentao_name: str, pool_set: set) -> tuple[str | None, bool]:
    """检查禅道名是否匹配池中姓名

    Returns:
        (pool_name, is_ambiguous)
        - pool_name: 匹配到的池名，或 None
        - is_ambiguous: 需用户确认才可自动关注
    """
    cn_parts = extract_chinese_names(zentao_name)
    for cn in cn_parts:
        if cn in pool_set:
            ambiguous = False
            # 情况1：多个中文片段（如 ['艾博连', '孙超']），带有公司/外协前缀
            if len(cn_parts) > 1:
                ambiguous = True
            else:
                # 情况2：原始名去掉中文后剩余部分含数字（如 李涛2→李涛），可能是重名
                remainder = zentao_name
                for part in cn_parts:
                    remainder = remainder.replace(part, '', 1)
                if re.search(r'\d', remainder):
                    ambiguous = True
            return (cn, ambiguous)
    return (None, False)


def match_pool_names(unfocused_persons: list, focus_list: list = None) -> dict:
    """检查未关注人员是否有在全局池中的，返回自动关注和待确认两个列表

    Returns:
        {'auto_focused': [...], 'ambiguous': [...]}
        - auto_focused: 池中只有1人匹配，可直接关注
        - ambiguous: 池名匹配到多个禅道人员（如李涛/李涛2），需用户确认
    """
    if focus_list is None:
        focus_list = []
    pool = load_focus_pool()
    if not pool:
        return {'auto_focused': [], 'ambiguous': []}
    pool_set = set(pool)

    # 对每个池中姓名，找到所有匹配的未关注人员
    from collections import defaultdict
    pool_to_matches = defaultdict(list)
    pool_ambiguous = defaultdict(bool)  # 是否有匹配项带前缀
    for name in unfocused_persons:
        matched, is_amb = _match_pool_name(name, pool_set)
        if matched:
            pool_to_matches[matched].append(name)
            if is_amb:
                pool_ambiguous[matched] = True

    auto_focused = []
    ambiguous = []
    for cn, matches in pool_to_matches.items():
        total_matches = len(matches)
        # 去重（同名+同名2算重名）
        unique_base = set()
        for m in matches:
            import re
            unique_base.add(re.sub(r'\d+$', '', m))
        has_duplicate = len(unique_base) < total_matches or total_matches > 1

        if has_duplicate or pool_ambiguous[cn]:
            # 重名或带前缀，需要确认
            any_focused = any(m in focus_list for m in matches)
            if not any_focused:
                ambiguous.append({'pool_name': cn, 'matches': matches, 'reason': 'prefix' if pool_ambiguous[cn] else 'duplicate'})
        else:
            auto_focused.append(matches[0])

    return {'auto_focused': auto_focused, 'ambiguous': ambiguous}
