# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## 项目概述

禅道BUG数据分析工具，支持本地文件上传分析，生成统计报表。

## 运行命令

```bash
# GUI界面分析（主程序 - PyQt6版本）
cd D:\ai\test\zentao_bug_analysis
python zentao_bug_tool_v2_qt.py

# CLI分析
python analyze.py --project-id 304
python analyze.py --all-projects
```

## 版本历史

### v1.0 (当前基础版本)
- **主程序**: `zentao_bug_tool_v2_qt.py` (PyQt6 GUI)
- **备份位置**: `versions/zentao_bug_tool_v2_qt_v1.0.py`

**功能特性**:
- Mac风格现代UI设计
- 按人员分组统计BUG（总数、激活、已解决、已关闭、A/B/C/D级）
- 关注人员功能（✔标记选中状态）
- 自动加载对应项目的关注列表（C62Xlist.json、C52Xlist.json等）
- 点击BUG详情跳转禅道网页
- 状态筛选（全部/激活/已解决/已关闭）
- 严重程度筛选（A/B/C/D级）
- 搜索人员功能
- 导出报表功能

## 架构

### 核心模块

| 文件 | 功能 |
|------|------|
| `zentao_bug_tool_v2_qt.py` | **主程序** - PyQt6 GUI：本地文件分析、数据筛选、人员勾选、导出报表 |
| `zentao_bug_tool_v2.py` | 旧版本Tkinter GUI（保留兼容） |
| `zentao_crawler.py` | 爬虫（已禁用下载功能，仅保留结构） |
| `analyze.py` | CLI分析工具：项目BUG统计、人员归属、高优先级BUG筛选 |

### 数据流向

```
本地文件（xlsx/csv）
    ↓
zentao_bug_tool_v2_qt.py 解析
    ↓
按人员分组统计 → 输出报表
```

### 依赖

- PyQt6: GUI界面
- tkinter: GUI界面（Python内置，用于旧版本）
- bs4 (BeautifulSoup4): HTML解析（analyze.py 使用）
- requests: HTTP请求（analyze.py 使用）

## 配置说明

### 关注列表文件命名规则

文件名中包含项目标识时，自动加载对应关注列表：

| 文件名标识 | 关注列表文件 |
|-----------|-------------|
| C62 | C62Xlist.json |
| C52 | C52Xlist.json |
| B30X-E11 | B30X-E11list.json |

### 禅道BUG链接格式

点击BUG详情时跳转：`https://zd.bicv.com/bug-view-{bugID}.html`
