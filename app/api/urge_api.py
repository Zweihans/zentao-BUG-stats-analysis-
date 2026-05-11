"""AI 催办文案 API"""
import re
from datetime import date
from fastapi import APIRouter, HTTPException
from app.services.ai_client import call_ai, test_connection, get_ai_config, update_ai_config

router = APIRouter(tags=["urge"])

STYLE_PROMPTS = {
    "formal": "请用正式、专业的措辞，适合企业微信/钉钉工作群场景。语气尊重但不生硬，直奔主题。",
    "casual": "请用轻松、口语化的措辞，像同事之间日常聊天一样。可以适当使用表情符号。",
    "brief": "请用极其简洁的措辞，一句话带过统计，其余只列关键 BUG 编号和链接。",
}

TEMPLATE = '''你是项目 {project_name} 的 BUG 跟进助手。请根据以下数据生成工作提醒，核心是**让研发一眼看清自己手头 BUG 的延期情况和紧急程度**。

【项目名称】{project_name}
【文案风格要求】{style_instruction}
{extra_instruction}
【人员 BUG 数据】
{data_text}

紧急程度由两个维度决定：
- 严重度：S > A > B > C
- 截止日期：已延期的 > 临近截止的 > 未到期的

输出要求：
1. 标题用 `【{project_name}】`，不要出现"催办"二字
2. 按人员分段，每位以 @人名 开头
3. 每人先写一行总结，突出已延期数量和最高严重度
4. BUG 按紧急程度排列（S已延期 > A已延期 > S未延期 > A未延期 > B/C已延期 > 其余）
5. 已延期的 BUG 必须标注"延期X天"，这是最重要的信息
6. 未到期的 BUG 不需要提及截止状态，正常列出即可
7. 每个 BUG 列出：级别标签、编号、标题、链接；已延期的额外加截止日期和延期天数
8. S/A 级与 B/C 级之间空行隔开
9. 不要分析 BUG 的技术内容或功能模块，只关注延期和严重度
10. 只输出最终文案，不要额外说明'''


def _parse_date(val: str) -> str:
    """尝试从各种格式中提取日期"""
    if not val:
        return ''
    # 匹配 YYYY-MM-DD 或 YYYY/MM/DD
    m = re.search(r'(\d{4})[-/](\d{1,2})[-/](\d{1,2})', val)
    if m:
        return f'{m.group(1)}-{m.group(2).zfill(2)}-{m.group(3).zfill(2)}'
    # 匹配连续8位数字
    m = re.search(r'(\d{4})(\d{2})(\d{2})', val)
    if m:
        return f'{m.group(1)}-{m.group(2)}-{m.group(3)}'
    return ''


def _overdue_days(deadline_str: str) -> int | None:
    """计算延期天数：今天 - 截止日期，正数表示已延期"""
    d = _parse_date(deadline_str)
    if not d:
        return None
    try:
        dl = date.fromisoformat(d)
        return (date.today() - dl).days
    except Exception:
        return None


def _deadline_label(deadline_str: str) -> str:
    """返回截止日期标签，仅在已延期时有内容"""
    overdue = _overdue_days(deadline_str)
    if overdue is None:
        return ''
    if overdue > 0:
        return f'已延期{overdue}天'
    # 未延期的不标注
    return ''


def _urgency_key(b: dict) -> tuple:
    """排序键：S已延期 > A已延期 > S未延期 > A未延期 > B/C已延期 > 其余"""
    sev_order = {'S': 0, 'A': 1, 'B': 2, 'C': 3}
    sev = sev_order.get(b.get('severity', 'C'), 9)
    overdue = _overdue_days(b.get('deadline', ''))
    is_sa = 0 if sev <= 1 else 1  # S/A first
    has_overdue = 0 if (overdue is not None and overdue > 0) else 1  # overdue first
    overdue_val = -(overdue if overdue is not None and overdue > 0 else 0)  # most overdue first
    return (is_sa, has_overdue, overdue_val, sev)


def _build_data_text(targets: list) -> str:
    """将目标人员 BUG 数据转为 AI 可读文本，聚焦延期和严重度"""
    lines = []
    for p in targets:
        active = [b for b in (p.get('bugs') or []) if _is_active(b.get('status', ''))]
        if not active:
            continue
        active.sort(key=_urgency_key)

        s_count = sum(1 for b in active if b.get('severity') == 'S')
        a_count = sum(1 for b in active if b.get('severity') == 'A')
        b_count = sum(1 for b in active if b.get('severity') == 'B')
        c_count = sum(1 for b in active if b.get('severity') == 'C')

        overdue_bugs = []
        for b in active:
            od = _overdue_days(b.get('deadline', ''))
            if od is not None and od > 0:
                overdue_bugs.append((b['id'], od))
        max_overdue = max([od for _, od in overdue_bugs]) if overdue_bugs else 0

        lines.append(f'\n=== {p["name"]} ===')
        lines.append(f'激活BUG: {len(active)} | S:{s_count} A:{a_count} B:{b_count} C:{c_count} | 已延期: {len(overdue_bugs)}个 | 最长延期: {max_overdue}天')
        lines.append('')

        for b in active:
            sev = b.get('severity', '-')
            dl_label = _deadline_label(b.get('deadline', ''))
            dl_str = f' **{dl_label}**' if dl_label else ''
            parts = [f'#{b["id"]} [{sev}]{dl_str}']
            parts.append(f'\n  标题: {b.get("title", "")}')
            parts.append(f'\n  链接: https://zd.bicv.com/bug-view-{b["id"]}.html')
            lines.append(' '.join(parts))
        lines.append('')
    return '\n'.join(lines)


def _is_active(st: str) -> bool:
    s = st.lower()
    return 'closed' not in s and '已关闭' not in s and 'resolved' not in s and '已解决' not in s


@router.post("/urge/generate")
async def generate_urge_text(data: dict):
    """AI 生成催办文案"""
    targets = data.get('targets', [])
    project_name = data.get('project_name', '')
    style = data.get('style', 'formal')
    extra_prompt = data.get('extra_prompt', '').strip()

    if not targets:
        raise HTTPException(400, "缺少目标人员数据")

    style_instruction = STYLE_PROMPTS.get(style, STYLE_PROMPTS['formal'])
    extra_instruction = f'【额外要求】{extra_prompt}' if extra_prompt else ''

    data_text = _build_data_text(targets)

    if not data_text.strip():
        return {"text": "没有激活 BUG", "source": "none"}

    prompt = TEMPLATE.format(
        project_name=project_name.replace('{', '{{').replace('}', '}}'),
        style_instruction=style_instruction.replace('{', '{{').replace('}', '}}'),
        extra_instruction=extra_instruction.replace('{', '{{').replace('}', '}}'),
        data_text=data_text.replace('{', '{{').replace('}', '}}'),
    )

    try:
        result = call_ai(
            system_prompt='你是一个项目 BUG 催办助手。你的任务是把 BUG 数据整理成清晰的催办消息，让研发人员一眼看出哪些 BUG 最紧急、哪些已延期。不要分析 BUG 的技术内容，只关注严重程度和截止日期延期的紧急程度。',
            user_prompt=prompt,
            temperature=0.7,
            max_tokens=2000,
            timeout=30
        )
        return {"text": result.strip(), "source": "ai"}
    except Exception as e:
        # 降级：返回空标记，前端自行生成模板文案
        return {"text": "", "source": "fallback", "error": str(e)[:200]}


@router.get("/ai/config")
async def get_ai_config_api():
    return get_ai_config()


@router.put("/ai/config")
async def update_ai_config_api(data: dict):
    """保存 AI 配置到 .env 文件"""
    base_url = data.get('base_url', '').strip()
    api_key = data.get('api_key', '').strip()
    model = data.get('model', '').strip()

    try:
        update_ai_config(base_url, api_key, model)
        return {"ok": True}
    except Exception as e:
        raise HTTPException(500, str(e))


@router.post("/ai/test")
async def test_ai_connection():
    return test_connection()
