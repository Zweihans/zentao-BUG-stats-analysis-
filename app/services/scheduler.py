"""定时任务调度器"""
import os
import queue
import threading
import asyncio
from datetime import datetime
from apscheduler.schedulers.asyncio import AsyncIOScheduler

_scheduler = None
LOG_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "logs")


def _get_scheduler():
    global _scheduler
    if _scheduler is None:
        _scheduler = AsyncIOScheduler()
    return _scheduler


def _run_scheduled_import_all():
    """定时导入所有关注项目（串行，避免并行导致 ZenTao 会话冲突）"""
    from app.services.cookie_manager import get_cookie, has_cookie
    if not has_cookie():
        _log("system", "没有 Cookie，跳过")
        return

    from app.stores.project_store import load_projects
    projects = [p for p in load_projects() if p.get('focus')]
    if not projects:
        _log("system", "没有关注项目，跳过")
        return

    cookie = get_cookie()
    from app.api.import_api import _run_import

    for p in projects:
        pid = p['id']
        pname = p.get('name', pid)
        _log(pid, f"开始导入 ({pname})")
        q = queue.Queue()
        t = threading.Thread(target=_run_import, args=(pid, cookie, q), daemon=True)
        t.start()

        try:
            while t.is_alive():
                try:
                    msg = q.get(timeout=1)
                    if isinstance(msg, dict) and msg.get('type') == 'complete':
                        _log(pid, f"完成 ({pname})")
                        break
                    if isinstance(msg, dict) and msg.get('type') == 'error':
                        _log(pid, f"失败 ({pname}): {msg.get('message', '未知')}")
                        break
                except queue.Empty:
                    pass
            t.join()
        except Exception as e:
            _log(pid, f"异常 ({pname}): {e}")


def _log(project_id: str, message: str):
    os.makedirs(LOG_DIR, exist_ok=True)
    log_file = os.path.join(LOG_DIR, "scheduler.log")
    ts = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    line = f"[{ts}] 项目{project_id}: {message}\n"
    try:
        with open(log_file, 'a', encoding='utf-8') as f:
            f.write(line)
    except Exception:
        pass


def refresh_schedule():
    scheduler = _get_scheduler()
    for job in list(scheduler.get_jobs()):
        if job.id.startswith("import_project"):
            scheduler.remove_job(job.id)

    from app.services.config_store import get_config
    config = get_config()
    if not config.get('schedule_enabled'):
        return

    hour = config.get('schedule_hour', 9)

    from app.stores.project_store import load_projects
    projects = [p for p in load_projects() if p.get('focus')]
    if not projects:
        _log("system", "调度器未启用: 没有关注项目")
        return

    scheduler.add_job(
        _run_scheduled_import_all,
        'cron',
        hour=hour,
        minute=7,
        id="import_all_projects"
    )

    names = [p.get('name', p['id']) for p in projects]
    _log("system", f"调度器已刷新: {len(projects)}个项目 ({', '.join(names)})，每天{hour}:07 串行执行")


def start_scheduler():
    if os.environ.get('WERKZEUG_RUN_MAIN') == 'true':
        return

    scheduler = _get_scheduler()
    if not scheduler.running:
        scheduler.start()
        refresh_schedule()


def stop_scheduler():
    global _scheduler
    if _scheduler and _scheduler.running:
        _scheduler.shutdown(wait=False)
        _scheduler = None
