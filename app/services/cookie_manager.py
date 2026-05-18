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

    pw = None
    browser = None
    context = None
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

        update_cookie_status(result[0], result[1])
        page.close()
        return result

    except Exception as e:
        msg = f"连接失败: {e}"
        update_cookie_status(False, msg)
        return (False, msg)
    finally:
        if context:
            try: context.close()
            except Exception: pass
        if browser:
            try: browser.close()
            except Exception: pass
        if pw:
            try: pw.stop()
            except Exception: pass


def has_cookie() -> bool:
    return get_cookie() is not None


# 缓存 cookie 检测结果，避免每次页面加载都启动 Playwright
_cookie_status_cache = {"valid": None, "last_checked": None, "message": "", "dismissed_at": None}
_status_file = os.path.join(BASE_DIR, "logs", "cookie_status.json")


def _load_cookie_status_from_disk():
    """从磁盘恢复 cookie 验证状态（避免重启后丢失）"""
    import json as _json
    if os.path.exists(_status_file):
        try:
            with open(_status_file, 'r', encoding='utf-8') as f:
                data = _json.load(f)
            _cookie_status_cache["valid"] = data.get("valid")
            _cookie_status_cache["last_checked"] = data.get("last_checked")
            _cookie_status_cache["message"] = data.get("message", "")
            _cookie_status_cache["dismissed_at"] = data.get("dismissed_at")
        except Exception:
            pass


def _save_cookie_status_to_disk():
    """持久化 cookie 验证状态"""
    import json as _json
    os.makedirs(os.path.dirname(_status_file), exist_ok=True)
    try:
        with open(_status_file, 'w', encoding='utf-8') as f:
            _json.dump(_cookie_status_cache, f, ensure_ascii=False)
    except Exception:
        pass


_load_cookie_status_from_disk()


def get_cookie_status() -> dict:
    """获取 cookie 状态（轻量，不触发 Playwright）"""
    if not has_cookie():
        return {"has_cookie": False, "valid": False, "last_checked": None, "message": "尚未配置 Cookie，无法下载数据"}
    return {
        "has_cookie": True,
        "valid": _cookie_status_cache["valid"],
        "last_checked": _cookie_status_cache["last_checked"],
        "message": _cookie_status_cache["message"],
        "dismissed_at": _cookie_status_cache["dismissed_at"],
    }


def update_cookie_status(valid: bool, message: str) -> None:
    """更新缓存的 cookie 验证状态"""
    from datetime import datetime
    _cookie_status_cache["valid"] = valid
    _cookie_status_cache["last_checked"] = datetime.now().isoformat()
    _cookie_status_cache["message"] = message
    _save_cookie_status_to_disk()


def dismiss_cookie_warning():
    """标记 cookie 预警已关闭（持久化，跨重启可靠）"""
    from datetime import datetime
    _cookie_status_cache["dismissed_at"] = datetime.now().isoformat()
    _save_cookie_status_to_disk()
