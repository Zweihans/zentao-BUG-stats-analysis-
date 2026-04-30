"""FastAPI 应用主入口"""
import os
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
STATIC_DIR = os.path.join(BASE_DIR, "static")

app = FastAPI(title="禅道BUG分析工具", version="3.0.0")

from app.api import projects, analyze, focus, import_api, export, trend
app.include_router(projects.router, prefix="/api")
app.include_router(analyze.router, prefix="/api")
app.include_router(focus.router, prefix="/api")
app.include_router(import_api.router, prefix="/api")
app.include_router(export.router, prefix="/api")
app.include_router(trend.router, prefix="/api")


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




# 静态文件挂载（必须在最后）
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")


@app.get("/{full_path:path}")
async def spa(full_path: str):
    """SPA 回退路由"""
    target = os.path.join(STATIC_DIR, full_path)
    if os.path.isfile(target):
        return FileResponse(target)
    return FileResponse(os.path.join(STATIC_DIR, "index.html"))
