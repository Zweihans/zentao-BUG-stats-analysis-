#!/usr/bin/env python3
"""
禅道BUG爬虫
使用Cookie直接访问已登录状态的禅道，抓取BUG列表数据
"""

import requests
from bs4 import BeautifulSoup
import json
import csv
import re
import time
from datetime import datetime
from urllib.parse import urljoin
from pathlib import Path

# ============== 配置区域 ==============
# 请修改以下配置
ZENDAO_URL = "https://zd.bicv.com"  # 禅道地址

# 从浏览器复制Cookie
# 格式: key1=value1; key2=value2
COOKIE = "device=desktop; hideMenu=false; keepLogin=on; lang=zh-cn; lastProject=708; preBranch=0; preProductID=331; tab=project; theme=default; vision=rnd; za=wangxinghao; zentaosid=15d823ea5845efa8b72a1491771a9d57; zp=1088dc075190572e1ab4be18f69807922187cd38"
# =====================================


class ZentaoCrawler:
    def __init__(self, base_url, cookie):
        self.base_url = base_url.rstrip('/')
        self.cookie = cookie
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Cookie': self.cookie
        })

    def check_login(self) -> bool:
        """检查Cookie是否有效"""
        print(f"[{datetime.now().strftime('%H:%M:%S')}] 检查Cookie有效性...")

        # 尝试访问禅道首页或我的页面
        check_urls = [
            f"{self.base_url}/my.html",
            f"{self.base_url}/index.html",
            f"{self.base_url}/"
        ]

        for url in check_urls:
            try:
                resp = self.session.get(url, timeout=10, allow_redirects=False)
                # 如果没有重定向到登录页，说明Cookie有效
                if resp.status_code == 200 and 'login' not in resp.url.lower():
                    print(f"[{datetime.now().strftime('%H:%M:%S')}] Cookie有效!")
                    return True
            except:
                continue

        print(f"[{datetime.now().strftime('%H:%M:%S')}] Cookie可能已失效")
        return False

    def get_bug_list_page(self, page=1) -> str:
        """获取BUG列表页面HTML"""
        # 禅道BUG列表URL - 使用用户提供的格式
        bug_url = f"{self.base_url}/bug-browse-304.html"
        params = {
            'page': page,
            'orderBy': 'id_desc',
            'recPerPage': '100'
        }

        resp = self.session.get(bug_url, params=params, timeout=10)

        # 保存HTML到文件用于调试
        with open("debug_page.html", "w", encoding="utf-8") as f:
            f.write(resp.text)
        print(f"[调试] HTML已保存到 debug_page.html, URL: {resp.url}, 状态码: {resp.status_code}")

        return resp.text

    def parse_bug_list(self, html: str) -> list:
        """解析BUG列表HTML，返回BUG数据列表"""
        bugs = []
        soup = BeautifulSoup(html, 'html.parser')

        # 尝试多种表格选择器（不同禅道版本可能不同）
        table = soup.find('table', {'class': 'table'})
        if not table:
            table = soup.find('table', {'id': 'bugList'})
        if not table:
            table = soup.find('table', {'class': 'table-bordered'})

        if not table:
            # 如果没找到表格，打印页面结构帮助调试
            print("[调试] 未找到BUG表格，页面结构如下:")
            print(soup.body.get_text()[:500] if soup.body else "无法获取页面内容")
            return bugs

        rows = table.find_all('tr')
        for row in rows[1:]:  # 跳过表头
            cols = row.find_all('td')
            if len(cols) < 5:
                continue

            try:
                bug = {}

                # BUG ID - 通常在第一列
                id_link = cols[0].find('a')
                if id_link:
                    bug['id'] = id_link.get_text(strip=True)
                    bug['link'] = urljoin(self.base_url, id_link.get('href', ''))

                # BUG标题
                bug['title'] = cols[1].get_text(strip=True) if len(cols) > 1 else ''

                # 严重程度
                bug['severity'] = cols[2].get_text(strip=True) if len(cols) > 2 else ''

                # 优先级
                bug['priority'] = cols[3].get_text(strip=True) if len(cols) > 3 else ''

                # 状态
                bug['status'] = cols[4].get_text(strip=True) if len(cols) > 4 else ''

                # 创建者
                bug['openedBy'] = cols[5].get_text(strip=True) if len(cols) > 5 else ''

                # 指派给
                bug['assignedTo'] = cols[6].get_text(strip=True) if len(cols) > 6 else ''

                # 创建时间
                bug['openedDate'] = cols[7].get_text(strip=True) if len(cols) > 7 else ''

                if bug.get('id'):
                    bugs.append(bug)

            except Exception as e:
                print(f"解析行数据出错: {e}")
                continue

        return bugs

    def get_total_pages(self, html: str) -> int:
        """从页面中提取总页数"""
        soup = BeautifulSoup(html, 'html.parser')

        # 尝试查找分页信息
        pager = soup.find('div', {'class': 'pager'})
        if pager:
            match = re.search(r'(\d+)/(\d+)', pager.get_text())
            if match:
                return int(match.group(2))

        # 尝试查找最后一页链接
        last_link = soup.find('a', text=re.compile(r'末页|尾页|last|>>', re.I))
        if last_link:
            href = last_link.get('href', '')
            match = re.search(r'page=(\d+)', href)
            if match:
                return int(match.group(1))

        # 尝试查找分页组件中的页码
        pagination = soup.find('ul', {'class': 'pagination'})
        if pagination:
            page_nums = pagination.find_all('a')
            max_page = 1
            for a in page_nums:
                match = re.search(r'(\d+)', a.get_text())
                if match:
                    max_page = max(max_page, int(match.group(1)))
            if max_page > 1:
                return max_page

        return 1

    def fetch_all_bugs(self, max_pages=50) -> list:
        """抓取所有BUG（支持翻页）"""
        all_bugs = []

        print(f"[{datetime.now().strftime('%H:%M:%S')}] 开始抓取BUG列表...")

        # 获取第一页，确定总页数
        html = self.get_bug_list_page(1)
        total_pages = self.get_total_pages(html)
        print(f"[{datetime.now().strftime('%H:%M:%S')}] 共 {total_pages} 页")

        bugs = self.parse_bug_list(html)
        all_bugs.extend(bugs)
        print(f"[{datetime.now().strftime('%H:%M:%S')}] 第1页: 获取到 {len(bugs)} 条BUG")

        # 抓取剩余页面
        for page in range(2, min(total_pages + 1, max_pages + 1)):
            time.sleep(0.5)  # 避免请求太快
            html = self.get_bug_list_page(page)
            bugs = self.parse_bug_list(html)
            all_bugs.extend(bugs)
            print(f"[{datetime.now().strftime('%H:%M:%S')}] 第{page}页: 获取到 {len(bugs)} 条BUG")

        return all_bugs

    def export_to_json(self, bugs: list, filepath: str):
        """导出为JSON"""
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(bugs, f, ensure_ascii=False, indent=2)
        print(f"[{datetime.now().strftime('%H:%M:%S')}] 已导出到 {filepath}")

    def export_to_csv(self, bugs: list, filepath: str):
        """导出为CSV"""
        if not bugs:
            return

        keys = bugs[0].keys()
        with open(filepath, 'w', encoding='utf-8-sig', newline='') as f:
            writer = csv.DictWriter(f, fieldnames=keys)
            writer.writeheader()
            writer.writerows(bugs)
        print(f"[{datetime.now().strftime('%H:%M:%S')}] 已导出到 {filepath}")


def main():
    print("=" * 50)
    print("禅道BUG爬虫 (Cookie方式)")
    print("=" * 50)

    crawler = ZentaoCrawler(ZENDAO_URL, COOKIE)

    if not crawler.check_login():
        print("Cookie无效，请重新获取")
        return

    bugs = crawler.fetch_all_bugs()

    if bugs:
        print(f"\n[{datetime.now().strftime('%H:%M:%S')}] 共抓取到 {len(bugs)} 条BUG")

        # 导出数据
        output_dir = Path(__file__).parent / 'data'
        output_dir.mkdir(exist_ok=True)

        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        crawler.export_to_json(output_dir / f'bugs_{timestamp}.json', bugs=bugs)
        crawler.export_to_csv(output_dir / f'bugs_{timestamp}.csv', bugs=bugs)
    else:
        print("未获取到任何BUG数据")


if __name__ == '__main__':
    main()
