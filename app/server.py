"""FastAPI 应用主入口"""
import os
import sys
import threading
import time
from contextlib import asynccontextmanager
from fastapi import FastAPI, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
STATIC_DIR = os.path.join(BASE_DIR, "static")


@asynccontextmanager
async def lifespan(app: FastAPI):
    try:
        from app.services.scheduler import start_scheduler
        start_scheduler()
    except Exception:
        pass
    yield
    try:
        from app.services.scheduler import stop_scheduler
        stop_scheduler()
    except Exception:
        pass


app = FastAPI(title="禅道BUG分析工具", version="3.2.0", lifespan=lifespan)

from app.api import projects, analyze, focus, import_api, export, trend, config_api, urge_api
app.include_router(projects.router, prefix="/api")
app.include_router(analyze.router, prefix="/api")
app.include_router(focus.router, prefix="/api")
app.include_router(import_api.router, prefix="/api")
app.include_router(export.router, prefix="/api")
app.include_router(trend.router, prefix="/api")
app.include_router(config_api.router, prefix="/api")
app.include_router(urge_api.router, prefix="/api")


@app.get("/api/health")
async def health():
    return {"status": "ok"}


@app.post("/api/cleanup")
async def cleanup_old_files():
    """清理 downloads 目录中的旧文件（非今天）"""
    from datetime import datetime
    downloads = os.path.join(BASE_DIR, "downloads")
    if not os.path.exists(downloads):
        return {"deleted": 0, "freed_mb": 0}

    today = datetime.now().strftime('%Y%m%d')
    deleted = 0
    freed = 0
    for f in os.listdir(downloads):
        filepath = os.path.join(downloads, f)
        if not os.path.isfile(filepath):
            continue
        if today in f:
            continue
        try:
            freed += os.path.getsize(filepath)
            os.remove(filepath)
            deleted += 1
        except Exception:
            pass

    return {"deleted": deleted, "freed_mb": round(freed / 1024 / 1024, 1)}


@app.get("/api/cache-info")
async def cache_info():
    """获取缓存信息"""
    downloads = os.path.join(BASE_DIR, "downloads")
    if not os.path.exists(downloads):
        return {"file_count": 0, "total_mb": 0}

    files = [f for f in os.listdir(downloads) if os.path.isfile(os.path.join(downloads, f))]
    total = sum(os.path.getsize(os.path.join(downloads, f)) for f in files)
    return {"file_count": len(files), "total_mb": round(total / 1024 / 1024, 1)}




@app.post("/api/restart")
async def restart_server():
    """重启服务（通过 os.execv 替换当前进程）"""
    def _do_restart():
        time.sleep(0.3)
        os.execv(sys.executable, [sys.executable] + sys.argv)
    threading.Thread(target=_do_restart, daemon=True).start()
    return {"ok": True}


# 静态文件挂载（必须在最后）
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")


@app.get("/{full_path:path}")
async def spa(full_path: str):
    """SPA 回退路由"""
    target = os.path.realpath(os.path.join(STATIC_DIR, full_path))
    root = os.path.realpath(STATIC_DIR)
    if not target.startswith(root + os.sep) and target != root:
        raise HTTPException(404, "Not found")
    if os.path.isfile(target):
        return FileResponse(target)
    return FileResponse(os.path.join(STATIC_DIR, "index.html"))
