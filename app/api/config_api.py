"""应用配置 API"""
from fastapi import APIRouter, HTTPException
from app.services.config_store import get_config, update_config

router = APIRouter(tags=["config"])


@router.get("/config")
async def config_get():
    return get_config()


@router.put("/config")
async def config_put(data: dict):
    hours = data.get('expiration_hours')
    if hours is not None:
        if not isinstance(hours, (int, float)) or hours < 1 or hours > 720:
            raise HTTPException(400, "过期时间需在 1-720 小时之间")
    update_config(data)
    try:
        from app.services.scheduler import refresh_schedule
        refresh_schedule()
    except Exception:
        pass
    return get_config()
