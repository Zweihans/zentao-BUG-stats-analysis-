"""报表导出 API"""
import os
import csv
import io
from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from app.services.file_reader import read_file
from app.services.bug_analyzer import severity_label
from app.stores.project_store import find_project

BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

router = APIRouter(tags=["export"])


@router.get("/export/{project_id}")
async def export_csv(project_id: str):
    """导出项目 BUG 数据为 CSV"""
    from app.api.analyze import find_latest_file

    project = find_project(project_id)
    if not project:
        raise HTTPException(404, "项目不存在")

    filepath = find_latest_file(project['name'])
    if not filepath:
        raise HTTPException(404, "没有可导出的数据，请先下载")

    bugs = read_file(filepath)
    if not bugs:
        raise HTTPException(404, "文件中无数据")

    output = io.StringIO()
    output.write('﻿')  # UTF-8 BOM

    fieldnames = ['id', 'title', 'severity', 'status', 'assignedTo']
    writer = csv.DictWriter(output, fieldnames=fieldnames, extrasaction='ignore')
    writer.writerow({
        'id': 'BUG ID',
        'title': '标题',
        'severity': '严重程度',
        'status': '状态',
        'assignedTo': '指派给',
    })
    for b in bugs:
        writer.writerow({
            'id': b.get('id', ''),
            'title': b.get('title', ''),
            'severity': severity_label(b.get('severity', 3)),
            'status': b.get('status', ''),
            'assignedTo': b.get('assignedTo', ''),
        })

    filename = f"bug_export_{project_id}.csv"
    return StreamingResponse(
        iter([output.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": f"attachment; filename={filename}"}
    )
