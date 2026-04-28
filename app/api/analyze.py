"""分析 API"""
import os
import json
from datetime import datetime
from fastapi import APIRouter, HTTPException
from app.stores.project_store import find_project, load_projects
from app.stores.focus_store import load_focus_list
from app.services.file_reader import read_file
from app.services.bug_analyzer import analyze
from app.services.diff_engine import find_previous_file, mark_new_bugs

BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
DOWNLOADS = os.path.join(BASE_DIR, "downloads")
LAST_STATE_FILE = os.path.join(BASE_DIR, "last_state.json")

router = APIRouter(tags=["analyze"])


def find_latest_file(project_id: str) -> str | None:
    """找到项目最新的下载文件"""
    if not os.path.exists(DOWNLOADS):
        return None

    prefix = project_id.lower()
    candidates = []
    for f in os.listdir(DOWNLOADS):
        if not (f.endswith('.xlsx') or f.endswith('.csv')):
            continue
        if prefix in f.lower():
            candidates.append((os.path.getmtime(os.path.join(DOWNLOADS, f)), f))

    if not candidates:
        return None
    candidates.sort(key=lambda x: x[0], reverse=True)
    return os.path.join(DOWNLOADS, candidates[0][1])


def extract_file_date(filepath: str) -> str:
    """从文件提取日期：优先文件名，兜底文件修改时间"""
    import re
    from datetime import datetime
    basename = os.path.basename(filepath)
    m = re.search(r'(\d{8})', basename)
    if m:
        d = m.group(1)
        return f"{d[:4]}-{d[4:6]}-{d[6:8]}"
    # 兜底：用文件修改时间
    try:
        ts = os.path.getmtime(filepath)
        return datetime.fromtimestamp(ts).strftime('%Y-%m-%d %H:%M')
    except Exception:
        return ""


@router.get("/analyze/{project_id}")
async def analyze_project(project_id: str):
    project = find_project(project_id)
    if not project:
        # 尝试从项目列表模糊查找
        projects = load_projects()
        for p in projects:
            if project_id.lower() in p.get('name', '').lower():
                project = p
                project_id = p['id']
                break

    if not project:
        raise HTTPException(404, "项目不存在")

    filepath = find_latest_file(project['name'])
    if not filepath:
        return {
            "project": project,
            "file_date": None,
            "total_bugs": 0,
            "total_persons": 0,
            "persons": [],
            "unfocused_persons": [],
            "stale": True,
            "message": "暂无数据，请前往导入页面下载",
        }

    bugs = read_file(filepath)
    prev_file = find_previous_file(filepath, project['name'])
    bugs = mark_new_bugs(bugs, prev_file)

    focus_list = load_focus_list(project_id)

    result = analyze(bugs, focus_list)
    result['project'] = {'id': project['id'], 'name': project['name'], 'focus': project.get('focus', False)}
    result['file_path'] = filepath
    result['file_date'] = extract_file_date(filepath)

    # 判断是否陈旧（不是今天的）
    today = datetime.now().strftime('%Y-%m-%d')
    result['stale'] = result['file_date'] != today

    # 保存最后状态
    try:
        with open(LAST_STATE_FILE, 'w', encoding='utf-8') as f:
            json.dump({'last_project_id': project['id']}, f, ensure_ascii=False)
    except Exception:
        pass

    return result


@router.get("/analyze/last-state")
async def get_last_state():
    try:
        if os.path.exists(LAST_STATE_FILE):
            with open(LAST_STATE_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
    except Exception:
        pass
    return {"last_project_id": None}


@router.post("/analyze")
async def analyze_file(data: dict):
    """分析指定文件"""
    file_path = data.get('file_path', '')
    project_id = data.get('project_id', '')

    if not os.path.exists(file_path):
        raise HTTPException(404, "文件不存在")

    bugs = read_file(file_path)
    prev_file = find_previous_file(file_path, project_id) if project_id else None
    bugs = mark_new_bugs(bugs, prev_file)

    focus_list = load_focus_list(project_id) if project_id else None

    result = analyze(bugs, focus_list)
    result['file_path'] = file_path
    result['file_date'] = extract_file_date(file_path)
    return result


@router.post("/compare")
async def compare_data(data: dict):
    """对比两天数据，返回新增 BUG ID 列表"""
    project_id = data.get('project_id', '')
    if not project_id:
        raise HTTPException(400, "缺少 project_id")

    today_file = find_latest_file(project_id)
    if not today_file:
        raise HTTPException(404, "未找到今日文件")

    prev_file = find_previous_file(today_file, project_id)
    if not prev_file:
        return {"new_ids": [], "message": "没有历史数据可供对比"}

    today_bugs = read_file(today_file)
    marked = mark_new_bugs(today_bugs, prev_file)
    new_ids = [b['id'] for b in marked if b.get('is_new')]
    return {"new_ids": new_ids, "total_new": len(new_ids)}
