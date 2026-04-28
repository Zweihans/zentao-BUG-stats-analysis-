"""对比引擎 - 比较今天和昨天的 BUG 列表，标记新增"""
import os
import glob as glob_mod

BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
DOWNLOADS = os.path.join(BASE_DIR, "downloads")


def find_previous_file(current_filepath: str, project_id: str) -> str | None:
    """找到同一项目最近的历史文件（不是今天的）"""
    if not os.path.exists(DOWNLOADS):
        return None

    current_name = os.path.basename(current_filepath)
    prefix = project_id.lower()

    candidates = []
    for f in os.listdir(DOWNLOADS):
        if not (f.endswith('.xlsx') or f.endswith('.csv')):
            continue
        if f == current_name:
            continue
        if prefix in f.lower():
            full = os.path.join(DOWNLOADS, f)
            candidates.append((os.path.getmtime(full), full))

    if not candidates:
        return None

    candidates.sort(key=lambda x: x[0], reverse=True)
    return candidates[0][1]


def mark_new_bugs(today_bugs: list, yesterday_file: str) -> list:
    """对比今天和昨天的 BUG，标记今天新增的 BUG

    Returns:
        标记后的 today_bugs（修改 is_new 字段）
    """
    from app.services.file_reader import read_file

    if not yesterday_file or not os.path.exists(yesterday_file):
        for b in today_bugs:
            b['is_new'] = False
        return today_bugs

    try:
        yesterday_bugs = read_file(yesterday_file)
    except Exception:
        for b in today_bugs:
            b['is_new'] = False
        return today_bugs

    yesterday_ids = {b['id'] for b in yesterday_bugs}

    for b in today_bugs:
        b['is_new'] = b['id'] not in yesterday_ids

    return today_bugs
