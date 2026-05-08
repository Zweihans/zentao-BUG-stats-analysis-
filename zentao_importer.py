#!/usr/bin/env python3
"""
禅道导入模块 - 使用Playwright从禅道网页导出BUG数据
"""

import os
import tempfile
import time
import threading
import asyncio
from typing import Optional, Callable


class ZentaoImporter:
    def __init__(self, base_url="https://zd.bicv.com"):
        self.base_url = base_url.rstrip('/')
        self.browser = None
        self.context = None
        self.page = None
        self.download_path = None
        self._download_url = None
        self.cancelled = False
        self._cancelled_lock = threading.Lock()

        # Cookie 由调用方通过 import_api 注入（get_cookie()），不在此硬编码
        self.cookie_str = ""

    def _parse_cookies(self) -> list:
        """解析cookie字符串为playwright需要的格式"""
        cookies = []
        for item in self.cookie_str.split(';'):
            item = item.strip()
            if '=' in item:
                name, value = item.split('=', 1)
                cookies.append({
                    'name': name.strip(),
                    'value': value.strip(),
                    'domain': 'zd.bicv.com',
                    'path': '/'
                })
        return cookies

    def _is_cancelled(self) -> bool:
        with self._cancelled_lock:
            return self.cancelled

    def connect(self) -> bool:
        """连接浏览器并登录禅道（同步版本）"""
        try:
            from playwright.sync_api import sync_playwright

            # 确保浏览器路径环境变量已设置（PyInstaller打包后需要）
            browsers_path = os.path.expanduser('~/AppData/Local/ms-playwright')
            if os.path.exists(browsers_path):
                os.environ['PLAYWRIGHT_BROWSERS_PATH'] = browsers_path

            print("[禅道导入] 正在启动浏览器...")
            playwright = sync_playwright().start()
            self.browser = playwright.chromium.launch(
                headless=True,
                timeout=15000,
                args=['--no-sandbox', '--disable-gpu', '--disable-blink-features=AutomationControlled']
            )
            print("[禅道导入] 浏览器已启动")

            self.context = self.browser.new_context(
                viewport={'width': 1920, 'height': 1080},
                user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
            )
            print("[禅道导入] 正在设置登录信息...")

            cookies = self._parse_cookies()
            self.context.add_cookies(cookies)

            self.page = self.context.new_page()
            self.playwright = playwright
            print("[禅道导入] 连接成功!")
            return True

        except Exception as e:
            print(f"[禅道导入] 连接失败: {e}")
            import traceback
            traceback.print_exc()
            raise Exception(f"连接禅道浏览器失败: {e}") from e

    def navigate_and_export(self, url: str, progress_callback: Callable = None) -> Optional[str]:
        """导航到指定页面并触发导出（同步版本）"""
        def do_callback(msg: str, prog: int):
            if progress_callback:
                try:
                    progress_callback(msg, prog)
                except:
                    pass

        try:
            print(f"[禅道导入] 正在打开页面: {url}")
            do_callback("正在打开禅道页面...", 10)

            self.page.goto(url, wait_until='domcontentloaded', timeout=60000)
            # 等待页面DOM稳定后再操作
            time.sleep(2)
            print("[禅道导入] 页面已加载")

            # 检查是否被重定向到登录页（cookie过期）
            if 'login' in self.page.url.lower():
                print("[禅道导入] 检测到登录页面，cookie可能已过期")
                raise Exception("登录会话已过期，请更新cookie")

            # 检查是否已取消
            if self._is_cancelled():
                print("[禅道导入] 操作已取消")
                return None

            # 动态检测可用的 iframe
            print("[禅道导入] 检测页面 iframe...")
            iframe_ids = self.page.evaluate("""() => {
                try {
                    return Array.from(document.querySelectorAll('iframe')).map(function(f) { return f.id || '(unnamed)'; });
                } catch(e) { return []; }
            }""")
            print(f"[禅道导入] 检测到 iframe: {iframe_ids}")

            # 优先匹配常见禅道 iframe ID，否则使用页面检测到的第一个
            preferred_ids = ['appIframe-qa', 'appIframe-admin', 'appIframe-bug', 'appIframe', 'iframe-qa']
            found_frame = None
            used_id = None

            # 先尝试优先 ID
            for fid in preferred_ids:
                if fid in iframe_ids:
                    try:
                        f = self.page.frame_locator(f'#{fid}')
                        f.locator('body').first.wait_for(timeout=5000)
                        found_frame = f
                        used_id = fid
                        break
                    except:
                        continue

            # 如果优先 ID 都不匹配，尝试任意检测到的 iframe
            if not found_frame and iframe_ids:
                for fid in iframe_ids:
                    if fid == '(unnamed)':
                        continue
                    try:
                        f = self.page.frame_locator(f'#{fid}')
                        f.locator('body').first.wait_for(timeout=5000)
                        found_frame = f
                        used_id = fid
                        break
                    except:
                        continue

            # 仍然没找到，尝试无 iframe 模式（直接在主页操作）
            if not found_frame:
                print("[禅道导入] 未找到可用 iframe，尝试在主页操作...")
                try:
                    self.page.locator('body').first.wait_for(timeout=5000)
                    found_frame = self.page  # 直接使用 page 对象
                    used_id = '(main page)'
                except:
                    pass

            if not found_frame:
                raise Exception(f"页面加载失败：未找到可用的内容区域。检测到的iframe: {iframe_ids}")

            print(f"[禅道导入] 使用内容区域: #{used_id}")
            is_main_page = (found_frame == self.page)
            do_callback("正在点击导出按钮...", 30)

            # 6. 点击导出按钮，展开下拉菜单
            # 支持多种可能的按钮文本和结构
            export_btn_selectors = [
                'button:has-text("导出")',
                'a:has-text("导出")',
                'button:has-text("导出数据")',
                'button[data-toggle*="dropdown"]:has-text("导出")',
                '.btn-group button:has-text("导出")',
                '[class*="export"] button',
                'button[title*="导出"]',
            ]

            export_btn_found = False
            for selector in export_btn_selectors:
                try:
                    if is_main_page:
                        btn = self.page.locator(selector).first
                    else:
                        btn = found_frame.locator(selector).first
                    btn.click(timeout=5000)
                    export_btn_found = True
                    print(f"[禅道导入] 通过选择器 '{selector}' 找到导出按钮")
                    break
                except:
                    continue

            if not export_btn_found:
                raise Exception(f"未找到'导出'按钮，已尝试: {', '.join(export_btn_selectors)}")

            time.sleep(0.5)

            # 检查是否已取消
            if self._is_cancelled():
                print("[禅道导入] 操作已取消")
                return None

            # 7. 点击"导出数据"菜单项
            print("[禅道导入] 选择'导出数据'选项...")
            export_menu_selectors = [
                'a:has-text("导出数据")',
                'li:has-text("导出数据")',
                'a:has-text("导出")',
                '.dropdown-menu a:has-text("导出")',
                '.dropdown-menu li:has-text("导出")',
            ]
            export_menu_found = False
            for selector in export_menu_selectors:
                try:
                    if is_main_page:
                        item = self.page.locator(selector).first
                    else:
                        item = found_frame.locator(selector).first
                    item.click(timeout=5000)
                    export_menu_found = True
                    print(f"[禅道导入] 通过选择器 '{selector}' 找到导出数据菜单")
                    break
                except:
                    continue

            if not export_menu_found:
                raise Exception(f"未找到'导出数据'菜单项，已尝试: {', '.join(export_menu_selectors)}")
            time.sleep(1)

            # 检查是否已取消
            if self._is_cancelled():
                print("[禅道导入] 操作已取消")
                return None

            print("[禅道导入] 导出对话框已打开")
            do_callback("正在等待服务器生成文件...", 50)

            # 先创建下载保存目录
            self.download_path = tempfile.mkdtemp(prefix="zentao_bug_")

            # 8. 点击导出确认按钮触发下载
            print("[禅道导入] 点击导出确认按钮并等待下载...")
            do_callback("正在等待下载链接...", 70)

            with self.page.expect_download(timeout=300000) as download_info:
                # 在 with 块内执行触发下载的操作
                modal_export_selectors = [
                    '.modal-content .btn.primary',
                    '.modal-footer .btn-primary',
                    '.modal .btn-primary',
                    'button:has-text("导出")',
                    '.modal button.btn-primary',
                    'button.btn-primary',
                ]
                modal_found = False
                for selector in modal_export_selectors:
                    try:
                        if is_main_page:
                            btn = self.page.locator(selector).first
                        else:
                            btn = found_frame.locator(selector).first
                        btn.click(timeout=5000)
                        modal_found = True
                        print(f"[禅道导入] 通过选择器 '{selector}' 找到确认导出按钮")
                        break
                    except:
                        continue

                if not modal_found:
                    raise Exception(f"未找到确认导出按钮，已尝试: {', '.join(modal_export_selectors)}")

                # 检查是否已取消
                if self._is_cancelled():
                    print("[禅道导入] 操作已取消")
                    return None

                download = download_info.value

            filename = download.suggested_filename
            print(f"[禅道导入] 文件已生成: {filename}")
            do_callback(f"正在下载文件: {filename}", 80)

            # 检查是否已取消
            if self._is_cancelled():
                print("[禅道导入] 操作已取消")
                return None

            # 保存文件（实际在此处等待浏览器完成下载，大文件可能较慢）
            save_path = os.path.join(self.download_path, filename)
            print(f"[禅道导入] 正在保存文件: {filename}")
            download.save_as(save_path)

            # 检查文件大小
            if os.path.exists(save_path):
                total_size = os.path.getsize(save_path)
                size_mb = total_size / 1024 / 1024
                print(f"[禅道导入] 下载完成! 文件大小: {size_mb:.1f} MB")
                do_callback(f"下载完成: {filename} ({size_mb:.1f} MB)", 100)

            return save_path

        except Exception as e:
            if self._is_cancelled():
                print("[禅道导入] 操作已取消")
                return None
            error_msg = f"导出过程出错: {e}"
            print(f"[禅道导入] {error_msg}")
            import traceback
            traceback.print_exc()
            raise Exception(error_msg) from e

    def cancel(self):
        """取消导入 - 强制关闭页面"""
        print("[禅道导入] 取消导入，设置取消标志")
        with self._cancelled_lock:
            self.cancelled = True
        # 强制关闭页面来中断阻塞操作
        try:
            if self.page:
                self.page.close()
                print("[禅道导入] 页面已强制关闭")
        except Exception as e:
            print(f"[禅道导入] 关闭页面出错: {e}")

    def close(self):
        """关闭浏览器（带超时保护，避免线程挂住）"""
        import signal
        print("[禅道导入] 正在关闭浏览器...")

        def _close_browser():
            try:
                if self.page:
                    self.page.close()
            except Exception:
                pass
            try:
                if self.context:
                    self.context.close()
            except Exception:
                pass
            try:
                if self.browser:
                    self.browser.close()
            except Exception:
                pass
            try:
                if hasattr(self, 'playwright') and self.playwright:
                    self.playwright.stop()
            except Exception:
                pass

        # 在独立线程中关闭，最多等 15 秒
        t = threading.Thread(target=_close_browser, daemon=True)
        t.start()
        t.join(timeout=15)

        if self.download_path and os.path.exists(self.download_path):
            try:
                import shutil
                shutil.rmtree(self.download_path, ignore_errors=True)
            except:
                pass
        print("[禅道导入] 浏览器已关闭")


def import_from_zentao(url: str, progress_callback: Callable = None) -> Optional[str]:
    """从禅道URL导入BUG数据的便捷函数（同步阻塞版本）"""
    importer = ZentaoImporter()
    try:
        importer.connect()
        return importer.navigate_and_export(url, progress_callback)
    finally:
        importer.close()


if __name__ == "__main__":
    def test_callback(msg, progress):
        print(f"[{progress}%] {msg}")

    test_url = "https://zd.bicv.com/bug-browse-304-all-unclosed-0-id_desc-0-20-1-bug-0.html"
    print(f"测试从禅道导入: {test_url}")
    result = import_from_zentao(test_url, test_callback)
    if result:
        print(f"下载成功: {result}")
    else:
        print("下载失败")
