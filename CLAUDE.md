# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## 项目概述

禅道BUG数据分析工具，网页版（FastAPI + 原生 JS SPA），支持多项目 BUG 下载、按人员分组统计、严重级别筛选、关注人员管理、柱状图/饼状图/趋势折线图、一键催办、周报生成、定时自动下载。

## 运行命令

```bash
cd D:\ai\test\zentao_bug_analysis

# 安装依赖
pip install fastapi uvicorn openpyxl apscheduler playwright python-multipart
playwright install chromium

# 启动服务
python main.py
```

浏览器自动打开 `http://127.0.0.1:8765`。

## 架构

```
main.py                  # 入口，uvicorn + 自动开浏览器
app/
├── server.py            # FastAPI 应用、lifespan（调度器启停）、静态文件 SPA 回退
├── api/                 # API 路由
│   ├── analyze.py       # 分析接口（GET/POST analyze, /compare, last-state）
│   ├── config_api.py    # 配置读写（过期时间、定时开关）
│   ├── export.py        # CSV 导出（按项目名匹配文件）
│   ├── focus.py         # 关注人员读写
│   ├── import_api.py    # 禅道导入/批量下载（SSE 进度推送）
│   ├── projects.py      # 项目管理 CRUD
│   └── trend.py         # 趋势数据 API
├── services/            # 业务逻辑
│   ├── bug_analyzer.py  # 按人员分组统计（S/A/B/C 计数、激活/已解决/已关闭分类）
│   ├── config_store.py  # 应用配置持久化（.app_config.json）
│   ├── cookie_manager.py# Cookie 存储与验证
│   ├── diff_engine.py   # 新旧 BUG 对比，标记 is_new
│   ├── exporter.py      # 报表导出逻辑
│   ├── file_reader.py   # xlsx/csv 解析（zipfile+XML 直接解析，不依赖 openpyxl）
│   ├── scheduler.py     # APScheduler 定时任务（串行下载所有关注项目）
│   └── trend_store.py   # 趋势数据 upsert（按日期覆盖）
└── stores/              # 数据持久化
    ├── focus_store.py   # 关注人员列表（{project_id}list.json）
    └── project_store.py # 项目配置（import_projects.json）
static/
├── index.html           # SPA 入口
├── css/style.css        # 样式
└── js/
    ├── api.js           # API 请求封装（EventSource SSE）
    ├── app.js           # 主逻辑：数据分析、图表、催办、周报、邮件报告
    ├── batch.js         # 批量下载页
    └── settings.js      # 项目管理/设置页
zentao_importer.py       # Playwright 禅道下载引擎
```

## 数据流向

```
禅道网页（Playwright 自动化）
    ↓ 导出 xlsx
downloads/ 目录
    ↓ file_reader.py 解析
bug_analyzer.py 按人员分组统计
    ↓
API JSON → 前端 app.js 渲染
    ↓
趋势数据 → trends/{project_id}_trend.json（每次导入自动记录）
```

## 关键设计

### 文件匹配规则
- `find_latest_file(project_name)` — 用项目名（如 "C52X-E14"）在 downloads/ 中匹配最新文件
- 排除以当前项目名为前缀的更长的项目名（如 "C52X" 不会匹配 "C52X-E14" 的文件）
- 调用时务必传入 `project['name']`，不能传数字 ID

### 严重程度映射
- 禅道原生值：1=致命(S), 2=严重(A), 3=一般(B), 4=轻微(C)
- 内部存储：0=S, 1=A, 2=B, 3=C（`parse_severity` 做 `num-1` 归一化）
- 前端显示：S, A, B, C

### Cookie 管理
- Cookie 通过设置页手动输入并保存
- 所有 Playwright 浏览器实例共用同一 Cookie
- 定时任务串行下载避免会话冲突

### 调度器
- APScheduler AsyncIOScheduler，每天指定时间执行一次
- 单个 cron job 串行处理所有 `focus=true` 的项目
- 通过 `WERKZEUG_RUN_MAIN` 检测避免 uvicorn reload 双进程

### 前端版本号
- 静态资源通过 `?v=3.1.0` 管理缓存，更新后在 index.html 中升级版本号

## 配置说明

### 关注列表
- 按项目 ID 存储：`{project_id}list.json`（如 `1list.json`, `2list.json`）
- 默认文件：`focus_list.json`
- `is_focused` 使用子串匹配（支持部分名称匹配）

### 项目配置
- `import_projects.json`：项目名称、禅道 URL、focus 标记
- `.app_config.json`：过期时间、定时开关、定时小时

### 禅道 BUG 链接
`https://zd.bicv.com/bug-view-{bugID}.html`
