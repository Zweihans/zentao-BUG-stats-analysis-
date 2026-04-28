# 禅道 BUG 分析工具

网页版禅道 BUG 数据分析工具，支持多项目 BUG 下载、按人员分组统计、严重级别筛选、关注人员管理、柱状图/饼状图可视化。

## 快速开始

```bash
pip install fastapi uvicorn playwright

playwright install chromium

python main.py
```

浏览器自动打开 `http://127.0.0.1:8765`。

## 功能页面

| 页面 | 功能 |
|------|------|
| **数据分析** | 按人员分组查看 BUG、S/A/B/C 严重级别筛选、关注/非关注分组、新增 BUG 标记、柱状图/饼状图 |
| **数据下载** | 勾选项目批量从禅道下载最新 BUG 数据（SSE 实时进度） |
| **项目管理** | 添加/编辑/删除禅道项目 |
| **设置** | Cookie 配置与验证、缓存清理 |

## 使用流程

1. **设置** → 粘贴禅道 Cookie（F12 → Application → Cookies → zentaosid 值）
2. **项目管理** → 添加禅道项目（名称 + Bug 列表 URL）
3. **数据下载** → 勾选项目 → 开始下载
4. **数据分析** → 选择项目查看 BUG 统计
5. 点击 **管理关注** → 勾选需要关注的人员 → 保存

## 项目结构

```
├── main.py              # 入口，uvicorn + 自动开浏览器
├── app/
│   ├── server.py        # FastAPI 应用
│   ├── api/             # API 路由
│   │   ├── analyze.py   # 分析接口
│   │   ├── export.py    # CSV 导出
│   │   ├── focus.py     # 关注人员
│   │   ├── import_api.py # 导入/批量下载
│   │   └── projects.py  # 项目管理
│   ├── services/        # 业务逻辑
│   │   ├── bug_analyzer.py
│   │   ├── cookie_manager.py
│   │   ├── diff_engine.py
│   │   ├── file_reader.py
│   │   └── exporter.py
│   └── stores/          # 数据持久化
│       ├── focus_store.py
│       └── project_store.py
├── static/
│   ├── index.html       # SPA 入口
│   ├── css/style.css    # Expo 风格设计系统
│   └── js/              # 前端逻辑
│       ├── api.js       # API 封装
│       ├── app.js       # 主逻辑 + 图表
│       ├── batch.js     # 批量下载
│       └── settings.js  # 项目管理
├── zentao_importer.py   # Playwright 禅道下载引擎
└── 启动.bat             # Windows 一键启动
```

## 技术栈

- **后端**: FastAPI + Playwright（禅道自动化）
- **前端**: 纯 HTML/CSS/JS（零框架）+ Chart.js（图表）
- **实时通信**: Server-Sent Events（SSE）推送下载进度
