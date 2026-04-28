"""报表导出 API"""
import os
import csv
import io
from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from app.services.file_reader import read_file
from app.services.bug_analyzer import analyze
from app.stores.focus_store import load_focus_list

BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

router = APIRouter(tags=["export"])


@router.get("/export/{project_id}")
async def export_csv(project_id: str):
    """导出项目 BUG 数据为 CSV"""
    downloads_dir = os.path.join(BASE_DIR, "downloads")
    if not os.path.exists(downloads_dir):
        raise HTTPException(404, "没有可导出的数据")

    # 找最新的 xlsx 文件
    xlsx_files = [f for f in os.listdir(downloads_dir) if f.endswith('.xlsx')]
    if not xlsx_files:
        raise HTTPException(404, "没有可导出的数据文件")

    # 按修改时间排序，取最新
    xlsx_files.sort(key=lambda f: os.path.getmtime(os.path.join(downloads_dir, f)), reverse=True)
    filepath = os.path.join(downloads_dir, xlsx_files[0])

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
            'severity': b.get('severity', ''),
            'status': b.get('status', ''),
            'assignedTo': b.get('assignedTo', ''),
        })

    filename = f"bug_export_{project_id}.csv"
    return StreamingResponse(
        iter([output.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": f"attachment; filename={filename}"}
    )
