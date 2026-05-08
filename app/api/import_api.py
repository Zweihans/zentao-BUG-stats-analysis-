"""导入 API — 禅道数据下载 + SSE 进度推送"""
import os
import sys
import json
import queue
import threading
import asyncio
from datetime import datetime
from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from app.stores.project_store import find_project
from app.services.cookie_manager import get_cookie, has_cookie

BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
# 确保可以导入项目根目录的 zentao_importer
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

router = APIRouter(tags=["import"])


def _run_import(project_id: str, cookie: str, q: queue.Queue):
    """在后台线程中运行导入"""
    import shutil
    import zentao_importer as zi

    def progress_cb(msg: str, pct: int):
        q.put({"type": "progress", "project": project_id, "percent": pct, "message": msg})

    importer = zi.ZentaoImporter()
    if cookie:
        importer.cookie_str = cookie

    try:
        importer.connect()
        project = find_project(project_id)
        if not project:
            q.put({"type": "error", "project": project_id, "message": "项目不存在"})
            return

        url = project.get('url', '')
        if not url:
            q.put({"type": "error", "project": project_id, "message": "项目URL未配置"})
            return

        filepath = importer.navigate_and_export(url, progress_cb)
        if filepath:
            # 复制到 downloads 目录（临时目录会被 importer.close() 清理）
            q.put({"type": "progress", "project": project_id, "percent": 85, "message": "正在复制文件..."})
            downloads_dir = os.path.join(BASE_DIR, "downloads")
            os.makedirs(downloads_dir, exist_ok=True)
            saved_path = os.path.join(downloads_dir, os.path.basename(filepath))
            shutil.copy2(filepath, saved_path)

            # 记录趋势数据
            q.put({"type": "progress", "project": project_id, "percent": 90, "message": "正在记录趋势..."})
            try:
                from app.services.file_reader import read_file
                from app.services.bug_analyzer import analyze
                from app.services.trend_store import save_trend_record
                from app.stores.focus_store import load_focus_list
                bugs = read_file(saved_path)
                fl = load_focus_list(project_id)
                result = analyze(bugs, fl)
                today = datetime.now().strftime('%Y-%m-%d')
                save_trend_record(project_id, today, result)
            except Exception:
                pass  # 趋势记录失败不影响导入流程

            q.put({
                "type": "complete",
                "project": project_id,
                "filename": os.path.basename(saved_path),
                "filepath": saved_path,
                "size_mb": round(os.path.getsize(saved_path) / 1024 / 1024, 1)
            })
        else:
            q.put({"type": "error", "project": project_id, "message": "下载失败：未获取到文件"})
    except Exception as e:
        q.put({"type": "error", "project": project_id, "message": str(e)})
    finally:
        try:
            importer.close()
        except Exception:
            pass  # 关闭失败不影响流程


async def _sse_generator(project_id: str) -> str:
    """SSE 事件生成器（带超时和客户端断开保护）"""
    import asyncio as _asyncio
    import time as _time

    cookie = get_cookie()
    if not cookie:
        yield f": connected\nevent: error\ndata: {json.dumps({'message': 'Cookie 未配置，请前往项目管理页面设置'})}\n\n"
        await _asyncio.sleep(0.01)
        return

    q = queue.Queue()
    thread = threading.Thread(target=_run_import, args=(project_id, cookie, q), daemon=True)
    thread.start()

    start = _time.monotonic()
    try:
        while True:
            elapsed = _time.monotonic() - start
            if elapsed > 600:  # 10分钟硬超时
                yield f"event: error\ndata: {json.dumps({'message': '导入超时，请重试'})}\n\n"
                thread.join(timeout=2)
                return
            try:
                data = await asyncio.get_event_loop().run_in_executor(None, lambda: q.get(timeout=0.5))
                yield f"event: {data['type']}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"
                if data['type'] in ('complete', 'error'):
                    break
            except queue.Empty:
                if not thread.is_alive():
                    break
                yield f": heartbeat\n\n"
    except _asyncio.CancelledError:
        # 客户端断开，后台线程为 daemon 会自动随进程退出
        return

    thread.join(timeout=2)


@router.get("/import/{project_id}/stream")
async def stream_import(project_id: str):
    project = find_project(project_id)
    if not project:
        raise HTTPException(404, "项目不存在")

    return StreamingResponse(
        _sse_generator(project_id),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        }
    )


async def _batch_sse(project_ids: list[str]) -> str:
    """批量下载 SSE 生成器（带超时和客户端断开保护）"""
    import asyncio as _asyncio
    import time as _time

    cookie = get_cookie()
    if not cookie:
        yield f": connected\nevent: error\ndata: {json.dumps({'message': 'Cookie 未配置'})}\n\n"
        await _asyncio.sleep(0.01)
        return

    total = len(project_ids)
    completed = 0
    results = []
    batch_start = _time.monotonic()

    try:
        for pid in project_ids:
            project = find_project(pid)
            if not project:
                results.append({"project": pid, "status": "error", "message": "项目不存在"})
                completed += 1
                yield f"event: project_done\ndata: {json.dumps({'project': pid, 'status': 'error', 'overall': {'done': completed, 'total': total}}, ensure_ascii=False)}\n\n"
                continue

            q = queue.Queue()
            thread = threading.Thread(target=_run_import, args=(pid, cookie, q), daemon=True)
            thread.start()

            proj_start = _time.monotonic()
            while True:
                if _time.monotonic() - proj_start > 600:
                    yield f"event: error\ndata: {json.dumps({'project': pid, 'message': '单个项目导入超时'}, ensure_ascii=False)}\n\n"
                    results.append({"project": pid, "status": "error", "message": "超时"})
                    break
                if _time.monotonic() - batch_start > 3600:
                    yield f"event: error\ndata: {json.dumps({'message': '批量导入总超时'}, ensure_ascii=False)}\n\n"
                    results.append({"project": pid, "status": "error", "message": "总超时"})
                    break
                try:
                    data = await asyncio.get_event_loop().run_in_executor(None, lambda: q.get(timeout=0.5))
                    data['overall'] = {'done': completed, 'total': total}
                    yield f"event: {data['type']}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"
                    if data['type'] == 'complete':
                        results.append({"project": pid, "status": "ok", "filename": data.get('filename', '')})
                        break
                    elif data['type'] == 'error':
                        results.append({"project": pid, "status": "error", "message": data.get('message', '')})
                        break
                except queue.Empty:
                    if not thread.is_alive():
                        break
                    yield f": heartbeat\n\n"

            thread.join(timeout=2)
            completed += 1
    except _asyncio.CancelledError:
        pass  # 客户端断开，daemon 线程自动清理

    yield f"event: batch_complete\ndata: {json.dumps({'results': results, 'done': completed, 'total': total}, ensure_ascii=False)}\n\n"
    await asyncio.sleep(0.01)


@router.get("/batch/stream")
async def stream_batch(ids: str = ""):
    """批量下载 SSE — ids 为逗号分隔的项目ID"""
    if not ids:
        raise HTTPException(400, "缺少项目ID列表")

    project_ids = [pid.strip() for pid in ids.split(',') if pid.strip()]
    if not project_ids:
        raise HTTPException(400, "项目ID列表为空")

    return StreamingResponse(
        _batch_sse(project_ids),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        }
    )


@router.get("/cookie")
async def check_cookie():
    return {"has_cookie": has_cookie()}


@router.put("/cookie")
async def update_cookie(data: dict):
    from app.services.cookie_manager import save_cookie
    cookie = data.get('cookie', '')
    if not cookie:
        raise HTTPException(400, "Cookie 不能为空")
    save_cookie(cookie)
    return {"success": True}


@router.post("/cookie/verify")
async def verify_cookie_endpoint(data: dict):
    from app.services.cookie_manager import verify_cookie, save_cookie
    cookie = data.get('cookie', '')
    if not cookie:
        cookie = get_cookie()
    if not cookie:
        raise HTTPException(400, "没有可检测的 Cookie")

    valid, msg = await asyncio.get_event_loop().run_in_executor(None, verify_cookie, cookie)
    if valid:
        save_cookie(cookie)
    return {"valid": valid, "message": msg}
