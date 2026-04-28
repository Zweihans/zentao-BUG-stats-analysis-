#!/usr/bin/env python3
"""
禅道BUG分析工具
用于分析禅道bug报告和关联车机日志
"""

import argparse
import json
import re
import time
from collections import defaultdict
from datetime import datetime
from pathlib import Path

import requests
from bs4 import BeautifulSoup

# 复用 zentao_crawler.py 的配置
from zentao_crawler import ZENDAO_URL as ZENTAO_URL, COOKIE


class ZentaoAnalyzer:
    def __init__(self):
        self.base_url = ZENTAO_URL.rstrip('/')
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Cookie': COOKIE
        })

    def check_login(self) -> bool:
        """检查Cookie是否有效"""
        print(f"[{datetime.now().strftime('%H:%M:%S')}] 检查Cookie有效性...")
        for url in [f"{self.base_url}/my.html", f"{self.base_url}/index.html"]:
            try:
                resp = self.session.get(url, timeout=10, allow_redirects=False)
                if resp.status_code == 200 and 'login' not in resp.url.lower():
                    print(f"[{datetime.now().strftime('%H:%M:%S')}] Cookie有效!")
                    return True
            except:
                continue
        print(f"[{datetime.now().strftime('%H:%M:%S')}] Cookie可能已失效")
        return False

    def get_project_list(self) -> list:
        """获取项目列表"""
        print(f"[{datetime.now().strftime('%H:%M:%S')}] 获取项目列表...")
        projects = []
        try:
            # 尝试访问项目列表页面
            resp = self.session.get(f"{self.base_url}/project-browse-0.html", timeout=10)
            soup = BeautifulSoup(resp.text, 'html.parser')

            # 解析项目列表
            for a in soup.find_all('a', href=re.compile(r'/project-view-\d+\.html')):
                href = a.get('href', '')
                match = re.search(r'project-view-(\d+)', href)
                if match:
                    pid = match.group(1)
                    name = a.get_text(strip=True)
                    if name:
                        projects.append({"id": pid, "name": name})

            # 去重
            seen = set()
            unique = []
            for p in projects:
                if p['id'] not in seen:
                    seen.add(p['id'])
                    unique.append(p)
            projects = unique

        except Exception as e:
            print(f"获取项目列表失败: {e}")
        return projects

    def get_bug_list_page(self, project_id: str, page: int = 1) -> str:
        """获取指定项目的BUG列表页面HTML"""
        bug_url = f"{self.base_url}/project-bug-{project_id}.html"
        params = {
            'page': page,
            'orderBy': 'id_desc',
            'recPerPage': '100'
        }
        resp = self.session.get(bug_url, params=params, timeout=10)
        return resp.text

    def get_total_pages(self, html: str) -> int:
        """从页面中提取总页数"""
        soup = BeautifulSoup(html, 'html.parser')
        pager = soup.find('div', {'class': 'pager'})
        if pager:
            match = re.search(r'(\d+)/(\d+)', pager.get_text())
            if match:
                return int(match.group(2))
        return 1

    def parse_bug_list(self, html: str) -> list:
        """解析BUG列表HTML，返回BUG数据列表"""
        bugs = []
        soup = BeautifulSoup(html, 'html.parser')

        table = soup.find('table', {'class': 'table'})
        if not table:
            table = soup.find('table', {'id': 'bugList'})
        if not table:
            table = soup.find('table', {'class': 'table-bordered'})

        if not table:
            return bugs

        rows = table.find_all('tr')
        for row in rows[1:]:
            cols = row.find_all('td')
            if len(cols) < 7:
                continue

            try:
                bug = {}

                # BUG ID
                id_link = cols[0].find('a')
                if id_link:
                    bug['id'] = id_link.get_text(strip=True)

                # BUG标题
                bug['title'] = cols[1].get_text(strip=True) if len(cols) > 1 else ''

                # 严重程度
                bug['severity'] = cols[2].get_text(strip=True) if len(cols) > 2 else ''

                # 优先级 (cols[3])
                bug['priority'] = cols[3].get_text(strip=True) if len(cols) > 3 else ''

                # 状态 (cols[4])
                bug['status'] = cols[4].get_text(strip=True) if len(cols) > 4 else ''

                # 创建者 (cols[5])
                bug['openedBy'] = cols[5].get_text(strip=True) if len(cols) > 5 else ''

                # 指派给 (cols[6])
                bug['assignedTo'] = cols[6].get_text(strip=True) if len(cols) > 6 else ''

                if bug.get('id'):
                    bugs.append(bug)
            except:
                continue

        return bugs

    def get_priority_value(self, priority_str: str) -> int:
        """将优先级字符串转为数字 (1=P0, 2=P1, 3=P2, 4=P3, 5=P4)"""
        priority_str = priority_str.lower().strip()
        if priority_str in ['1', 'p0', '高']:
            return 1
        elif priority_str in ['2', 'p1']:
            return 2
        elif priority_str in ['3', 'p2']:
            return 3
        elif priority_str in ['4', 'p3']:
            return 4
        elif priority_str in ['5', 'p4']:
            return 5
        # 尝试直接解析数字
        try:
            return int(priority_str[0])
        except:
            return 3

    def fetch_bugs_by_project(self, project_id: str, max_pages: int = 50) -> list:
        """抓取指定项目的所有BUG"""
        all_bugs = []

        try:
            html = self.get_bug_list_page(project_id, 1)
            total_pages = self.get_total_pages(html)
            total_pages = min(total_pages, max_pages)

            bugs = self.parse_bug_list(html)
            all_bugs.extend(bugs)

            for page in range(2, total_pages + 1):
                time.sleep(0.3)
                html = self.get_bug_list_page(project_id, page)
                bugs = self.parse_bug_list(html)
                all_bugs.extend(bugs)

        except Exception as e:
            print(f"抓取项目 {project_id} BUG失败: {e}")

        return all_bugs

    def analyze_project(self, project_id: str, project_name: str) -> dict:
        """分析单个项目的BUG统计"""
        bugs = self.fetch_bugs_by_project(project_id)

        owner_stats = defaultdict(lambda: {
            "total": 0, "high_priority": 0, "p0": 0, "p1": 0, "bugs": []
        })

        for bug in bugs:
            owner = bug.get('assignedTo', '未分配') or '未分配'
            priority_str = bug.get('priority', '3')
            priority_val = self.get_priority_value(priority_str)

            owner_stats[owner]["total"] += 1
            owner_stats[owner]["bugs"].append({
                "id": bug.get('id', ''),
                "title": bug.get('title', '')[:50],
                "priority": priority_val,
                "priority_str": priority_str
            })

            if priority_val in [1, 2]:
                owner_stats[owner]["high_priority"] += 1
                if priority_val == 1:
                    owner_stats[owner]["p0"] += 1
                else:
                    owner_stats[owner]["p1"] += 1

        return {
            "project_id": project_id,
            "project_name": project_name,
            "total_bugs": len(bugs),
            "owners": dict(owner_stats)
        }

    def analyze_all_projects(self) -> list:
        """分析所有项目"""
        projects = self.get_project_list()
        if not projects:
            print("未获取到项目列表")
            return []

        print(f"发现 {len(projects)} 个项目，开始统计BUG...")
        results = []

        for i, proj in enumerate(projects):
            print(f"[{i+1}/{len(projects)}] 正在分析: {proj['name']}")
            stats = self.analyze_project(proj['id'], proj['name'])
            results.append(stats)
            print(f"  -> {stats['total_bugs']}个BUG")

        return results


def format_reminder_text(stats_list: list) -> str:
    """生成提醒文本"""
    lines = []
    lines.append(f"📊 禅道BUG统计报表")
    lines.append(f"生成时间: {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    lines.append("=" * 50)

    total_high_priority = 0

    for stats in stats_list:
        lines.append(f"\n【{stats['project_name']}】(ID: {stats['project_id']})")
        lines.append(f"  总BUG数: {stats['total_bugs']}")

        sorted_owners = sorted(
            stats['owners'].items(),
            key=lambda x: (x[1]['high_priority'], x[1]['total']),
            reverse=True
        )

        for owner, data in sorted_owners:
            if data['total'] == 0:
                continue

            total_high_priority += data['high_priority']

            priority_tag = ""
            if data['p0'] > 0:
                priority_tag += f" 🔴P0×{data['p0']}"
            if data['p1'] > 0:
                priority_tag += f" 🟠P1×{data['p1']}"

            lines.append(f"  {owner}: {data['total']}个BUG{priority_tag}")

            if data['high_priority'] > 0:
                for bug in data['bugs']:
                    if bug['priority'] in [1, 2]:
                        pri_tag = "🔴P0" if bug['priority'] == 1 else "🟠P1"
                        lines.append(f"    {pri_tag} #{bug['id']} {bug['title']}")

    lines.append("\n" + "=" * 50)
    lines.append(f"汇总: 共 {total_high_priority} 个高优先级BUG待处理")

    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser(description='禅道BUG分析工具')
    parser.add_argument('--bug-id', help='分析指定BUG')
    parser.add_argument('--project-id', help='指定项目ID (多个用逗号分隔)')
    parser.add_argument('--all-projects', action='store_true', help='统计所有项目')
    parser.add_argument('--output', choices=['text', 'json'], default='text', help='输出格式')
    args = parser.parse_args()

    analyzer = ZentaoAnalyzer()

    if not analyzer.check_login():
        print("Cookie无效，请重新获取")
        return

    if args.bug_id:
        print(f"[{datetime.now().strftime('%H:%M:%S')}] 单BUG分析功能开发中...")
        print(f"BUG ID: {args.bug_id}")

    else:
        stats_list = []

        if args.all_projects:
            stats_list = analyzer.analyze_all_projects()

        elif args.project_id:
            project_ids = [p.strip() for p in args.project_id.split(",")]
            projects = analyzer.get_project_list()
            project_map = {p['id']: p['name'] for p in projects}

            for pid in project_ids:
                if not pid:
                    continue
                name = project_map.get(pid, pid)
                print(f"正在分析: {name}")
                stats = analyzer.analyze_project(pid, name)
                stats_list.append(stats)
                print(f"  -> {stats['total_bugs']}个BUG")

        else:
            print("请指定: --project-id 或 --all-projects")
            return

        if not stats_list:
            print("未获取到统计数据")
            return

        if args.output == 'json':
            print(json.dumps(stats_list, ensure_ascii=False, indent=2))
        else:
            print(format_reminder_text(stats_list))


if __name__ == '__main__':
    main()
