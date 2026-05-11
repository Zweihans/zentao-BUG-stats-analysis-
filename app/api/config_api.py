"""应用配置 API"""
from fastapi import APIRouter, HTTPException
from app.services.config_store import get_config, update_config

router = APIRouter(tags=["config"])


@router.get("/config")
async def config_get():
    return get_config()


VALID_KEYS = {'expiration_hours', 'schedule_enabled', 'schedule_hour', 'urge_style', 'urge_custom_prompt'}


@router.put("/config")
async def config_put(data: dict):
    hours = data.get('expiration_hours')
    if hours is not None:
        if not isinstance(hours, (int, float)) or hours < 1 or hours > 720:
            raise HTTPException(400, "过期时间需在 1-720 小时之间")
    # 只允许白名单内的字段
    filtered = {k: v for k, v in data.items() if k in VALID_KEYS}
    if filtered:
        update_config(filtered)
    try:
        from app.services.scheduler import refresh_schedule
        refresh_schedule()
    except Exception:
        pass
    return get_config()
