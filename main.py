#!/usr/bin/env python3
"""禅道BUG分析工具 - 网页版入口"""
import os
import sys
import webbrowser
import threading
import uvicorn

BASE_DIR = os.path.dirname(os.path.abspath(__file__))


def open_browser():
    webbrowser.open("http://127.0.0.1:8765")


def main():
    # 确保在项目目录运行
    os.chdir(BASE_DIR)

    # 延迟 800ms 打开浏览器，等服务器就绪
    threading.Timer(0.8, open_browser).start()
    print("禅道BUG分析工具启动: http://127.0.0.1:8765")

    uvicorn.run(
        "app.server:app",
        host="127.0.0.1",
        port=8765,
        log_level="info",
        reload=False
    )


if __name__ == "__main__":
    main()
