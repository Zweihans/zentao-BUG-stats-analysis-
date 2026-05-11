"""一次性从飞书 Wiki 提取所有 sheet 的姓名列，保存到本地 JSON"""
import json
import os
import sys
from playwright.sync_api import sync_playwright

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUTPUT = os.path.join(BASE_DIR, "feishu_names.json")

URLS = [
    "https://bicv-omosoft.feishu.cn/wiki/G9hlwC5m6in0JZka5QScasIAnYg",
    "https://bicv-omosoft.feishu.cn/wiki/QvRCwFzbviOOKFk3ufYcS2uDn3d",
    "https://bicv-omosoft.feishu.cn/wiki/Ng3AwwNfKi5U33kHIjqc2rzSnxS",
]


def extract_chinese_names(text: str) -> list[str]:
    """从文本中提取2-4字的纯中文姓名"""
    import re
    names = set()
    # 匹配2-4个连续中文字符
    for m in re.finditer(r'[一-鿿]{2,4}', text):
        name = m.group()
        # 过滤明显不是人名的词
        skip_words = {'文档', '表格', '数据', '页面', '加载', '搜索', '菜单', '撤销',
                      '重做', '格式', '插入', '拆分', '评论', '上传', '联系', '功能',
                      '默认', '查找', '替换', '分享', '最近', '修改', '知识库', '云文档',
                      '我的', '主页', '云盘', '智能', '纪要', '置顶', '新建', '软件',
                      '有限', '公司', '清单', '人员', '内部', '研发', '测试', '部门',
                      '负责', '姓名', '备注', '状态', '版本', '日期', '时间'}
        if name in skip_words:
            continue
        names.add(name)
    return sorted(names)


def process_page(page, url: str) -> set[str]:
    """处理一个飞书 wiki 页面，遍历所有 sheet 提取姓名"""
    all_names = set()
    print(f"\n{'='*60}")
    print(f"处理: {url}")

    try:
        page.goto(url, wait_until='networkidle', timeout=30000)
        page.wait_for_timeout(3000)
    except Exception as e:
        print(f"  页面加载超时: {e}")
        return all_names

    # 获取所有 sheet tab
    sheet_tabs = page.query_selector_all('[class*="sheet-tab"], [class*="sheetTab"], [class*="tab"], .tab-item, [role="tab"]')
    if not sheet_tabs:
        # 尝试找 sheet 切换器
        sheet_tabs = page.query_selector_all('.sheet-bar-item, .sheet-tab-item, [data-sheet]')

    if not sheet_tabs:
        # 没有子 sheet，直接提取当前页面
        print("  单 sheet 页面，直接提取...")
        names = _extract_from_current_sheet(page)
        all_names.update(names)
        print(f"  提取到 {len(names)} 个姓名: {names}")
        return all_names

    print(f"  找到 {len(sheet_tabs)} 个 sheet tab")
    tab_texts = []
    for tab in sheet_tabs:
        t = tab.inner_text().strip()
        if t:
            tab_texts.append(t)
    print(f"  Sheet 名称: {tab_texts}")

    # 遍历每个 sheet
    for i, tab in enumerate(sheet_tabs):
        try:
            tab_text = tab.inner_text().strip()
            if not tab_text:
                continue
            print(f"  [{i+1}/{len(sheet_tabs)}] 切换到 sheet: {tab_text}")
            tab.click()
            page.wait_for_timeout(2000)
            names = _extract_from_current_sheet(page)
            if names:
                print(f"    提取到 {len(names)} 个姓名")
            all_names.update(names)
        except Exception as e:
            print(f"    切换失败: {e}")

    return all_names


def _extract_from_current_sheet(page) -> set[str]:
    """从当前 sheet 提取姓名列"""
    names = set()

    # 方法1: 找表头中有"姓名"的列，读取该列所有值
    try:
        # 获取所有表格单元格
        cells = page.query_selector_all('td, th')
        header_row_indices = set()
        name_col_indices = set()

        # 先找表头行中"姓名"所在的列索引
        for i, cell in enumerate(cells):
            text = cell.inner_text().strip()
            if text == '姓名':
                # 找到同行的所有单元格来确定列索引
                row_cells = page.query_selector_all('tr')
                for row in row_cells:
                    row_cells_list = row.query_selector_all('td, th')
                    for j, rc in enumerate(row_cells_list):
                        if rc == cell or rc.inner_text().strip() == '姓名':
                            name_col_indices.add(j)
                            header_row_indices.add(row)

    except Exception:
        pass

    # 方法2: 直接遍历所有可见文本，提取中文姓名
    try:
        # 获取整个表格区域的文本
        sheet_content = page.query_selector('[class*="sheet"], [class*="table"], .sheet-container, table')
        if not sheet_content:
            sheet_content = page.query_selector('body')

        if sheet_content:
            text = sheet_content.inner_text()
            found = extract_chinese_names(text)
            names.update(found)
    except Exception as e:
        print(f"    提取文本失败: {e}")

    return names


def main():
    print("飞书姓名提取工具")
    print(f"输出文件: {OUTPUT}")
    print("\n请在弹出的浏览器中登录飞书，登录完成后按 Enter 继续...")

    input("按 Enter 开始...")

    with sync_playwright() as p:
        # 使用持久化上下文保存登录状态
        user_data_dir = os.path.join(BASE_DIR, ".playwright_feishu")
        context = p.chromium.launch_persistent_context(
            user_data_dir=user_data_dir,
            headless=False,
            args=['--no-sandbox'],
        )
        page = context.new_page()

        # 先打开飞书主页，让用户登录
        page.goto("https://bicv-omosoft.feishu.cn", wait_until='networkidle', timeout=30000)
        print("\n请在浏览器中完成飞书登录，然后按 Enter 继续...")
        input("登录完成后按 Enter...")

        all_names = {}
        for url in URLS:
            try:
                names = process_page(page, url)
                key = url.split('/')[-1].split('?')[0][:20]
                all_names[key] = sorted(names)
            except Exception as e:
                print(f"  处理失败: {e}")

        context.close()

    # 合并所有姓名
    merged = sorted(set().union(*all_names.values()))
    print(f"\n{'='*60}")
    print(f"总计提取到 {len(merged)} 个不重复姓名:")
    print(merged)

    # 保存
    with open(OUTPUT, 'w', encoding='utf-8') as f:
        json.dump(merged, f, ensure_ascii=False, indent=2)
    print(f"\n已保存到: {OUTPUT}")


if __name__ == '__main__':
    main()
