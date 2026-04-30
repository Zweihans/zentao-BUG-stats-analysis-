"""趋势 API"""
from fastapi import APIRouter, HTTPException
from app.services.trend_store import load_trend_data, delete_trend_data
from app.stores.project_store import find_project

router = APIRouter(tags=["trend"])


@router.get("/trend/{project_id}")
async def get_trend(project_id: str):
    project = find_project(project_id)
    if not project:
        raise HTTPException(404, "项目不存在")

    data = load_trend_data(project_id)
    if not data:
        return {"project_id": project_id, "records": []}
    return data


@router.delete("/trend/{project_id}")
async def clear_trend(project_id: str):
    project = find_project(project_id)
    if not project:
        raise HTTPException(404, "项目不存在")

    deleted = delete_trend_data(project_id)
    return {"deleted": deleted}
