"""xlsx/csv 文件读取"""
import csv
import re
import xml.etree.ElementTree as ET
import zipfile


def read_xlsx(filepath: str) -> tuple[list, int]:
    """读取 xlsx 文件，返回 (行列表, 表头行索引)"""
    with zipfile.ZipFile(filepath, 'r') as z:
        strings = []
        if 'xl/sharedStrings.xml' in z.namelist():
            root = ET.fromstring(z.read('xl/sharedStrings.xml'))
            ns = 'http://schemas.openxmlformats.org/spreadsheetml/2006/main'
            for si in root.findall(f'{{{ns}}}si'):
                t = si.find(f'{{{ns}}}t')
                if t is not None:
                    strings.append(t.text or '')
                else:
                    parts = [r.find(f'{{{ns}}}t') for r in si.findall(f'{{{ns}}}r')]
                    strings.append(''.join(p.text for p in parts if p is not None))

        root = ET.fromstring(z.read('xl/worksheets/sheet1.xml'))
        ns = 'http://schemas.openxmlformats.org/spreadsheetml/2006/main'
        rows = []
        for row in root.findall(f'.//{{{ns}}}row'):
            rd = []
            for c in row.findall(f'{{{ns}}}c'):
                t, v = c.get('t'), c.find(f'{{{ns}}}v')
                if t == 's' and v is not None:
                    rd.append(strings[int(v.text)] if int(v.text) < len(strings) else '')
                else:
                    rd.append(v.text or '' if v is not None else '')
            rows.append(rd)

    # 找到有最多非空单元格的行作为表头
    hi, mne = 0, 0
    for i, r in enumerate(rows):
        ne = len([v for v in r if v and v.strip()])
        if ne > mne:
            mne, hi = ne, i
    return rows, hi


def read_csv(filepath: str) -> tuple[list, int]:
    """读取 csv 文件，返回 (行列表, 表头行索引)"""
    with open(filepath, 'r', encoding='utf-8-sig', errors='replace') as f:
        rows = list(csv.reader(f))
    hi = 0
    for i, r in enumerate(rows):
        if any(v and v.strip() for v in r):
            hi = i
            break
    return rows, hi


def parse_headers(headers: list) -> dict:
    """解析表头，返回 {字段名: 列索引} 映射"""
    hi_map = {}
    for i, h in enumerate(headers):
        hc = str(h).strip()
        if not hc:
            continue
        hl = hc.lower()
        hi_map[hc] = i
        for key, aliases in [
            ('id', ['bug编号', 'bug编号', '编号', 'id']),
            ('title', ['bug标题', 'bug标题', '标题', 'title']),
            ('status', ['bug状态', 'bug状态', '子状态', 'status', '状态']),
            ('priority', ['优先级', 'bug优先级', 'priority', 'pri']),
            ('severity', ['严重程度', 'bug严重程度', 'severity']),
            ('assignedto', ['指派给', '批示复制', '指派人', '负责人', 'assignedto', 'assigned']),
        ]:
            if key not in hi_map:
                for a in aliases:
                    if hl == a.lower() or hl.endswith(a.lower()):
                        hi_map[key] = i
                        break
    return hi_map


def parse_severity(val: str) -> int:
    """解析严重程度为数字: 0=S, 1=A, 2=B, 3=C"""
    if not val:
        return 3
    val = str(val).strip()
    m = re.search(r'#(\d+)', val)
    if m:
        return int(m.group(1))
    try:
        return int(val)
    except ValueError:
        pass
    val_upper = val.upper()
    if val_upper == 'S':
        return 0
    elif val_upper == 'A':
        return 1
    elif val_upper == 'B':
        return 2
    elif val_upper == 'C':
        return 3
    return 3


def read_file(filepath: str) -> list:
    """读取文件，返回 BUG 记录列表"""
    if filepath.endswith('.xlsx'):
        rows, hi = read_xlsx(filepath)
    elif filepath.endswith('.csv'):
        rows, hi = read_csv(filepath)
    else:
        raise ValueError(f"不支持的文件格式: {filepath}")

    headers = rows[hi]
    hi_map = parse_headers(headers)

    idx = {k: hi_map.get(k, -1) for k in ['id', 'title', 'priority', 'severity', 'assignedto', 'status']}

    bugs = []
    for row in rows[hi + 1:]:
        if not row or not any(v and str(v).strip() for v in row if v):
            continue
        bug_id = str(row[idx['id']]).strip() if idx['id'] >= 0 and idx['id'] < len(row) else ''
        if not bug_id:
            continue

        bugs.append({
            'id': bug_id,
            'title': str(row[idx['title']]).strip() if idx['title'] >= 0 and idx['title'] < len(row) else '',
            'priority': parse_severity(str(row[idx['priority']]).strip() if idx['priority'] >= 0 and idx['priority'] < len(row) else ''),
            'severity': parse_severity(str(row[idx['severity']]).strip() if idx['severity'] >= 0 and idx['severity'] < len(row) else ''),
            'assignedTo': str(row[idx['assignedto']]).strip() if idx['assignedto'] >= 0 and idx['assignedto'] < len(row) else '未分配',
            'status': str(row[idx['status']]).strip() if idx['status'] >= 0 and idx['status'] < len(row) else '',
        })
    return bugs
