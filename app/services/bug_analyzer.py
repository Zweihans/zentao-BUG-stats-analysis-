"""BUG 分析逻辑 - 按人员分组统计"""
from collections import defaultdict


def severity_label(sev: int) -> str:
    """数字严重度转标签"""
    return {0: 'S', 1: 'A', 2: 'B', 3: 'C'}.get(sev, 'C')


def status_classify(status: str) -> str:
    """分类状态为: 激活 / 已解决 / 已关闭"""
    s = status.lower()
    if 'closed' in s or '已关闭' in s:
        return 'closed'
    if 'resolved' in s or '已解决' in s:
        return 'resolved'
    return 'active'


def analyze(bugs: list, focus_list: list = None) -> dict:
    """分析 BUG 列表，按人员分组

    Returns:
        {
            'total_bugs': int,
            'total_persons': int,
            'file_date': str (从文件名提取),
            'persons': [
                {
                    'name': str,
                    'total': int,
                    'A': int, 'B': int, 'C': int, 'D': int,
                    'active': int, 'resolved': int, 'closed': int,
                    'new_count': int,  # 今日新增数
                    'focus': bool,
                    'bugs': [
                        { 'id': str, 'title': str, 'severity': 'A'|'B'|'C'|'D',
                          'status': str, 'is_new': bool },
                        ...
                    ]
                },
                ...
            ]
        }
    """
    from app.stores.focus_store import is_focused

    owner_stats = defaultdict(lambda: {
        'total': 0, 'S': 0, 'A': 0, 'B': 0, 'C': 0,
        'active': 0, 'resolved': 0, 'closed': 0,
        'bugs': [], 'new_count': 0,
    })

    for b in bugs:
        owner = b.get('assignedTo', '未分配')
        sev = b.get('severity', 3)
        st = b.get('status', '')
        cls = status_classify(st)
        lab = severity_label(sev)

        owner_stats[owner]['total'] += 1
        owner_stats[owner][lab] = owner_stats[owner].get(lab, 0) + 1
        if cls == 'active':
            owner_stats[owner]['active'] += 1
        elif cls == 'resolved':
            owner_stats[owner]['resolved'] += 1
        elif cls == 'closed':
            owner_stats[owner]['closed'] += 1

        if b.get('is_new'):
            owner_stats[owner]['new_count'] += 1

        owner_stats[owner]['bugs'].append({
            'id': b['id'],
            'title': b.get('title', ''),
            'severity': lab,
            'status': st,
            'is_new': b.get('is_new', False),
            'openedDate': b.get('openedDate', ''),
            'deadline': b.get('deadline', ''),
        })

    # 排序：关注人员在前 + BUG 数降序
    fl = focus_list or []
    sorted_owners = sorted(
        owner_stats.items(),
        key=lambda x: (not is_focused(x[0], fl), -x[1]['total'])
    )

    persons = []
    for name, data in sorted_owners:
        data['name'] = name
        data['focus'] = is_focused(name, fl)
        # 按严重度排序 BUG
        data['bugs'].sort(key=lambda b: {'S': 0, 'A': 1, 'B': 2, 'C': 3}.get(b['severity'], 9))
        persons.append(data)

    return {
        'total_bugs': len(bugs),
        'total_persons': len(persons),
        'persons': persons,
        'unfocused_persons': [p['name'] for p in persons if not p['focus']],
    }
