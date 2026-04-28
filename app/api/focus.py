"""关注人员 API"""
from fastapi import APIRouter
from app.stores.focus_store import load_focus_list, save_focus_list

router = APIRouter(tags=["focus"])


@router.get("/focus/{project_id}")
async def get_focus(project_id: str = "default"):
    persons = load_focus_list(project_id if project_id != "default" else None)
    return {"persons": persons}


@router.put("/focus/{project_id}")
async def update_focus(project_id: str, data: dict):
    persons = data.get('persons', [])
    save_focus_list(persons, project_id if project_id != "default" else None)
    return {"success": True, "persons": persons}
