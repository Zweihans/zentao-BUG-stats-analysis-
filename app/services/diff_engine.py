"""对比引擎 - 比较今天和昨天的 BUG 列表，标记新增"""
import os
from datetime import datetime

BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
DOWNLOADS = os.path.join(BASE_DIR, "downloads")


def find_previous_file(current_filepath: str, project_name: str) -> str | None:
    """找到同一项目前一天（或更早）的最新文件，用于计算新增 BUG"""
    if not os.path.exists(DOWNLOADS):
        return None

    current_name = os.path.basename(current_filepath)
    prefix = project_name.lower()

    # 当日日期（按当前文件的 mtime 判断）
    today_ts = os.path.getmtime(current_filepath)
    today_date = datetime.fromtimestamp(today_ts).date()

    # 排除比当前项目名更长且以其为前缀的其他项目名（如 C52X vs C52X-E14）
    from app.stores.project_store import load_projects
    projects = load_projects()
    longer_names = []
    for p in projects:
        pname = p['name'].lower()
        if pname != prefix and pname.startswith(prefix):
            longer_names.append(pname)

    candidates = []
    for f in os.listdir(DOWNLOADS):
        if not (f.endswith('.xlsx') or f.endswith('.csv')):
            continue
        if f == current_name:
            continue
        f_lower = f.lower()
        if prefix not in f_lower:
            continue
        # 排除被更长项目名匹配到的文件
        skip = False
        for ln in longer_names:
            if ln in f_lower:
                skip = True
                break
        if skip:
            continue

        full = os.path.join(DOWNLOADS, f)
        file_mtime = os.path.getmtime(full)
        file_date = datetime.fromtimestamp(file_mtime).date()
        # 只取严格早于当日的文件（前一天、前两天...）
        if file_date >= today_date:
            continue
        candidates.append((file_mtime, full))

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
