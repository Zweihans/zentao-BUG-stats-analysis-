"""项目管理 API"""
import uuid
from fastapi import APIRouter, HTTPException
from app.stores.project_store import load_projects, save_projects, find_project

router = APIRouter(tags=["projects"])


@router.get("/projects")
async def list_projects():
    return {"projects": load_projects()}


@router.post("/projects")
async def add_project(data: dict):
    projects = load_projects()
    name = data.get('name', '').strip()
    if not name:
        raise HTTPException(400, "项目名称不能为空")

    new_id = uuid.uuid4().hex[:8]
    project = {
        'name': name,
        'url': data.get('url', ''),
        'focus': data.get('focus', False),
        'id': new_id,
    }
    projects.append(project)
    save_projects(projects)
    return {"success": True, "project": project}


@router.put("/projects/{project_id}")
async def update_project(project_id: str, data: dict):
    projects = load_projects()
    for p in projects:
        if p['id'] == project_id or p['name'] == project_id:
            if 'name' in data:
                p['name'] = data['name']
            if 'url' in data:
                p['url'] = data['url']
            if 'focus' in data:
                p['focus'] = data['focus']
            save_projects(projects)
            return {"success": True, "project": p}
    raise HTTPException(404, "项目不存在")


@router.delete("/projects/{project_id}")
async def delete_project(project_id: str):
    projects = load_projects()
    filtered = [p for p in projects if p['id'] != project_id and p['name'] != project_id]
    if len(filtered) == len(projects):
        raise HTTPException(404, "项目不存在")
    save_projects(filtered)
    return {"success": True}
