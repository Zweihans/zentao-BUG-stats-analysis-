"""将 SVG favicon 转为多尺寸 ICO 文件（使用 Playwright 渲染）"""
import struct
import io
import sys
from pathlib import Path
from playwright.sync_api import sync_playwright


def png_to_32bit_bmp(png_data: bytes, target_w: int, target_h: int) -> bytes:
    """将 PNG 数据解析为 32-bit ARGB BMP 数据（ICO 内嵌格式）"""
    # PNG 签名检查
    if png_data[:8] != b'\x89PNG\r\n\x1a\n':
        raise ValueError("不是有效的 PNG 文件")

    # 跳过 PNG IHDR，提取宽高
    # PNG: 8字节签名 | 4字节长度 | 4字节"IHDR" | 4字节宽 | 4字节高
    w = struct.unpack('>I', png_data[16:20])[0]
    h = struct.unpack('>I', png_data[20:24])[0]

    # 用简单的 RGBA 原始像素构建 BMP（通过 HTML Canvas 已经处理了缩放）
    # 这里我们依赖 Playwright 已经按目标尺寸截图
    # 我们需要从 PNG 提取原始 RGBA 数据

    # 使用 zlib 解压 IDAT 块，但更简单的是用 Png 库...
    # 实际上，最可靠的方法是用标准库解析 PNG

    # 改用更简单的方式：直接使用 Playwright 截图的 PNG
    # ICO 格式支持 PNG 内嵌（Vista+），这更简单
    return None  # placeholder


def create_ico_from_pngs(png_sizes: dict) -> bytes:
    """将多个尺寸的 PNG 打包为 ICO 文件（使用 PNG 内嵌，Vista+ 兼容）"""
    # ICO 使用 PNG 内嵌时：每个 entry 的 bpp=32，数据就是完整 PNG 文件
    images = []
    for size, png_data in sorted(png_sizes.items(), reverse=True):
        # 256 用 0 表示
        w = 0 if size >= 256 else size
        h = 0 if size >= 256 else size
        images.append((w, h, png_data))

    # ICO header
    buf = io.BytesIO()
    buf.write(struct.pack('<HHH', 0, 1, len(images)))  # reserved, type=icon, count

    # 计算数据偏移
    offset = 6 + len(images) * 16  # header + dir entries

    # 目录项
    img_entries = []
    for w, h, png_data in images:
        data_size = len(png_data)
        entry = struct.pack('<BBBBHHII', w, h, 0, 0, 1, 32, data_size, offset)
        img_entries.append(entry)
        buf.write(entry)
        offset += data_size

    # 图像数据
    for _, _, png_data in images:
        buf.write(png_data)

    return buf.getvalue()


def main():
    base = Path(__file__).resolve().parent.parent
    svg_path = base / 'static' / 'favicon.svg'
    ico_path = base / 'static' / 'favicon.ico'

    print(f'SVG: {svg_path}')
    print(f'ICO: {ico_path}')

    if not svg_path.exists():
        print(f'错误: 找不到 {svg_path}')
        sys.exit(1)

    svg_content = svg_path.read_text(encoding='utf-8')

    sizes = [16, 32, 48, 64, 256]
    png_sizes = {}

    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page()
        page.set_content(f'''
            <html><body style="margin:0;display:flex;align-items:center;justify-content:center;
            width:256px;height:256px;background:transparent;">
            <div id="icon">{svg_content}</div>
            </body></html>
        ''')

        for s in sizes:
            # 缩放 SVG 到目标尺寸
            page.evaluate(f'''
                document.getElementById('icon').style.width = '{s}px';
                document.getElementById('icon').style.height = '{s}px';
            ''')
            # 设置视口大小
            page.set_viewport_size({'width': s, 'height': s})
            # 截图
            screenshot = page.locator('#icon').screenshot(type='png')
            png_sizes[s] = screenshot
            print(f'  渲染 {s}x{s} — {len(screenshot)} bytes')

        browser.close()

    ico_data = create_ico_from_pngs(png_sizes)
    ico_path.write_bytes(ico_data)
    print(f'已生成: {ico_path} ({len(ico_data)} bytes)')

    # 更新桌面快捷方式图标
    desktop = Path.home() / 'Desktop' / '禅道BUG分析.lnk'
    if desktop.exists():
        import subprocess
        ps = f'''
$WshShell = New-Object -ComObject WScript.Shell
$Shortcut = $WshShell.CreateShortcut("{desktop}")
$Shortcut.IconLocation = "{ico_path}"
$Shortcut.Save()
Write-Host "快捷方式图标已更新"
'''
        subprocess.run(['powershell', '-Command', ps], capture_output=False)
        print(f'桌面快捷方式图标已更新')
    else:
        print(f'注意: 未找到桌面快捷方式 {desktop}')


if __name__ == '__main__':
    main()
