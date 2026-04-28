"""Cookie 安全管理"""
import os

BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
COOKIE_FILE = os.path.join(BASE_DIR, ".zentao_cookie")

# 除了 zentaosid 之外的支持性 cookie，保证页面正常渲染
DEFAULT_COOKIES = "device=desktop; hideMenu=false; keepLogin=on; lang=zh-cn; tab=project; theme=default; vision=rnd; za=wangxinghao"


def get_cookie() -> str | None:
    """链式查找 cookie: 环境变量 → 配置文件"""
    cookie = os.environ.get('ZENTAO_COOKIE', '')
    if cookie:
        return _normalize(cookie)

    if os.path.exists(COOKIE_FILE):
        try:
            with open(COOKIE_FILE, 'r', encoding='utf-8') as f:
                cookie = f.read().strip()
            if cookie:
                return _normalize(cookie)
        except Exception:
            pass

    return None


def save_cookie(cookie: str) -> None:
    """保存 cookie，自动识别裸 zentaosid 值并补全"""
    normalized = _normalize(cookie)
    os.makedirs(os.path.dirname(COOKIE_FILE), exist_ok=True)
    with open(COOKIE_FILE, 'w', encoding='utf-8') as f:
        f.write(normalized)


def _normalize(cookie: str) -> str:
    """如果输入只是 zentaosid 值（不含 =），自动补全为完整 cookie 字符串"""
    cookie = cookie.strip()
    if '=' not in cookie:
        cookie = f"zentaosid={cookie}; {DEFAULT_COOKIES}"
    return cookie


def parse_cookies(cookie_str: str, domain: str = "zd.bicv.com") -> list:
    """解析 cookie 字符串为 Playwright 格式"""
    cookies = []
    for item in cookie_str.split(';'):
        item = item.strip()
        if '=' in item:
            name, value = item.split('=', 1)
            cookies.append({
                'name': name.strip(),
                'value': value.strip(),
                'domain': domain,
                'path': '/'
            })
    return cookies


def verify_cookie(cookie_str: str) -> tuple[bool, str]:
    """验证 cookie 是否可用 — 尝试访问禅道首页"""
    from playwright.sync_api import sync_playwright

    cookie_str = _normalize(cookie_str)

    try:
        pw = sync_playwright().start()
        browser = pw.chromium.launch(headless=True, timeout=15000,
            args=['--no-sandbox', '--disable-gpu'])
        context = browser.new_context(
            viewport={'width': 1920, 'height': 1080},
            user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        )
        context.add_cookies(parse_cookies(cookie_str))
        page = context.new_page()
        page.goto("https://zd.bicv.com", wait_until='domcontentloaded', timeout=30000)

        if 'login' in page.url.lower():
            result = (False, "Cookie 已过期，请重新从浏览器复制")
        else:
            result = (True, "Cookie 有效")

        page.close()
        context.close()
        browser.close()
        pw.stop()
        return result

    except Exception as e:
        return (False, f"连接失败: {e}")


def has_cookie() -> bool:
    return get_cookie() is not None
