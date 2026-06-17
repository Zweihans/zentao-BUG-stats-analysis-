"""关注人员 API"""
import io
import os
from fastapi import APIRouter, File, UploadFile, HTTPException
from app.stores.focus_store import (
    load_focus_list, save_focus_list,
    load_focus_pool, merge_into_pool, match_pool_names,
    extract_chinese_names,
)
from app.stores.ignored_store import (
    get_ignored_unfocused, add_ignored_unfocused,
    get_ignored_ambiguous, add_ignored_ambiguous,
)

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


@router.get("/focus-pool")
async def get_pool():
    """获取全局应关注人员池"""
    pool = load_focus_pool()
    return {"names": pool, "count": len(pool)}


@router.post("/focus-pool/import")
async def import_focus_pool(file: UploadFile = File(...)):
    """上传 Excel/CSV 文件，提取各 sheet 的"姓名"列到全局池"""
    filename = (file.filename or '').lower()
    if not (filename.endswith('.xlsx') or filename.endswith('.csv')):
        raise HTTPException(400, "仅支持 .xlsx 或 .csv 文件")

    content = await file.read()
    names = set()

    if filename.endswith('.csv'):
        import csv
        text = content.decode('utf-8-sig', errors='replace')
        reader = csv.reader(io.StringIO(text))
        rows = list(reader)
        # 找"姓名"列的索引
        name_col = -1
        for row in rows:
            for i, cell in enumerate(row):
                if cell.strip() == '姓名':
                    name_col = i
                    break
            if name_col >= 0:
                break
        if name_col >= 0:
            for row in rows:
                if name_col < len(row):
                    val = row[name_col].strip()
                    if val and val != '姓名':
                        names.add(val)
        else:
            # 无姓名列，提取所有中文姓名
            for row in rows:
                for cell in row:
                    for cn in extract_chinese_names(cell.strip()):
                        if len(cn) >= 2:
                            names.add(cn)
    else:
        # xlsx — 用 zipfile + XML 解析
        import zipfile, xml.etree.ElementTree as ET
        try:
            with zipfile.ZipFile(io.BytesIO(content), 'r') as z:
                ns = 'http://schemas.openxmlformats.org/spreadsheetml/2006/main'
                r_ns = 'http://schemas.openxmlformats.org/officeDocument/2006/relationships'

                # 获取 shared strings
                strings = []
                if 'xl/sharedStrings.xml' in z.namelist():
                    root = ET.fromstring(z.read('xl/sharedStrings.xml'))
                    for si in root.findall(f'{{{ns}}}si'):
                        t = si.find(f'{{{ns}}}t')
                        if t is not None:
                            strings.append(t.text or '')
                        else:
                            parts = [r.find(f'{{{ns}}}t') for r in si.findall(f'{{{ns}}}r')]
                            strings.append(''.join(p.text for p in parts if p is not None))

                def _cell_value(c, strings):
                    """提取单元格值（支持 shared string、inline string、普通值）"""
                    v = c.find(f'{{{ns}}}v')
                    t = c.get('t', '')
                    if t == 's' and v is not None:
                        idx = int(v.text)
                        return strings[idx] if idx < len(strings) else ''
                    if t == 'inlineStr':
                        is_elem = c.find(f'{{{ns}}}is')
                        if is_elem is not None:
                            texts = [t.text or '' for t in is_elem.findall(f'.//{{{ns}}}t')]
                            return ''.join(texts)
                        return ''
                    if v is not None:
                        return v.text or ''
                    return ''

                # 获取 sheet 列表
                wb_root = ET.fromstring(z.read('xl/workbook.xml'))
                sheets = []
                for s_elem in wb_root.findall(f'.//{{{ns}}}sheet'):
                    sn = s_elem.get('name', '')
                    rid = s_elem.get(f'{{{r_ns}}}id', '')
                    sheets.append((sn, rid))

                # 解析关系文件
                rels = {}
                if 'xl/_rels/workbook.xml.rels' in z.namelist():
                    rel_root = ET.fromstring(z.read('xl/_rels/workbook.xml.rels'))
                    for rel in rel_root:
                        rels[rel.get('Id', '')] = rel.get('Target', '')

                # 遍历每个 sheet
                for sheet_name, rid in sheets:
                    target = rels.get(rid, f'worksheets/sheet{rid}.xml')
                    target = target.lstrip('/')
                    if not target.startswith('xl/'):
                        target = 'xl/' + target
                    if target not in z.namelist():
                        continue

                    sheet_root = ET.fromstring(z.read(target))
                    rows = sheet_root.findall(f'.//{{{ns}}}row')

                    # 先找姓名列
                    name_col = -1
                    name_row_idx = -1
                    for row_elem in rows:
                        r_idx = int(row_elem.get('r', 0))
                        for c in row_elem.findall(f'{{{ns}}}c'):
                            ref = c.get('r', '')
                            val = _cell_value(c, strings).strip()
                            if val == '姓名':
                                col_letter = ''.join(ch for ch in ref if ch.isalpha())
                                name_col = _col_to_idx(col_letter)
                                name_row_idx = r_idx
                                break
                        if name_col >= 0:
                            break

                    if name_col < 0:
                        continue

                    # 提取该 sheet 姓名列的所有值
                    for row_elem in rows:
                        r_idx = int(row_elem.get('r', 0))
                        if r_idx <= name_row_idx:
                            continue
                        for c in row_elem.findall(f'{{{ns}}}c'):
                            ref = c.get('r', '')
                            col_idx = _col_to_idx(''.join(ch for ch in ref if ch.isalpha()))
                            if col_idx == name_col:
                                val = _cell_value(c, strings).strip()
                                if val and val != '姓名':
                                    names.add(val)
        except Exception as e:
            raise HTTPException(400, f"文件解析失败: {e}")

    if not names:
        raise HTTPException(400, "未在任何 sheet 的'姓名'列中找到数据")

    added = merge_into_pool(list(names))
    total = len(load_focus_pool())
    return {
        "added": added,
        "total": total,
        "new_names": sorted(names)[:50],
    }


def _col_to_idx(col: str) -> int:
    """列字母转索引，A=0, B=1, ..."""
    idx = 0
    for ch in col.upper():
        idx = idx * 26 + (ord(ch) - ord('A') + 1)
    return idx - 1


@router.post("/focus-pool/auto-match")
async def auto_match_pool(data: dict):
    """检查未关注人员并自动匹配全局池"""
    project_id = data.get('project_id', '')
    unfocused = data.get('unfocused', [])
    focused = data.get('focused', [])

    if not project_id or not unfocused:
        return {"auto_focused": [], "ambiguous": []}

    # 过滤已被用户忽略的人员（包括手动取消关注的）
    ignored = get_ignored_unfocused(project_id)
    unfocused = [n for n in unfocused if n not in ignored]
    if not unfocused:
        return {"auto_focused": [], "ambiguous": []}

    result = match_pool_names(unfocused, focused)

    # 自动关注确定的人员
    if result.get('auto_focused'):
        current = load_focus_list(project_id if project_id != "default" else None)
        new_focus = list(current)
        for name in result['auto_focused']:
            if name not in new_focus:
                new_focus.append(name)
        save_focus_list(new_focus, project_id if project_id != "default" else None)

    return result


@router.post("/focus-pool/confirm-ambiguous")
async def confirm_ambiguous(data: dict):
    """用户确认重名关注"""
    project_id = data.get('project_id', '')
    selected = data.get('selected', [])  # [{pool_name, chosen_name}]

    if not project_id or not selected:
        return {"ok": False}

    current = load_focus_list(project_id if project_id != "default" else None)
    new_focus = list(current)
    for item in selected:
        name = item.get('chosen_name', '')
        if name and name not in new_focus:
            new_focus.append(name)

    save_focus_list(new_focus, project_id if project_id != "default" else None)
    return {"ok": True, "added": len(selected)}


# ========== 忽略记录（服务端持久化，不受浏览器/WebView2 影响） ==========

@router.get("/ignored/{project_id}")
async def get_ignored(project_id: str):
    return {
        "unfocused": get_ignored_unfocused(project_id),
        "ambiguous": get_ignored_ambiguous(project_id),
    }


@router.post("/ignored/{project_id}/unfocused")
async def save_ignored_unfocused(project_id: str, data: dict):
    names = data.get('names', [])
    if names:
        add_ignored_unfocused(project_id, names)
    return {"ok": True}


@router.post("/ignored/{project_id}/ambiguous")
async def save_ignored_ambiguous(project_id: str, data: dict):
    pool_names = data.get('pool_names', [])
    if pool_names:
        add_ignored_ambiguous(project_id, pool_names)
    return {"ok": True}
