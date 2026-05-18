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
| **数据分析** | 按人员分组查看 BUG、S/A/B/C 严重级别筛选、关注/非关注分组、新增 BUG 标记、柱状图/饼状图/趋势折线图、未关注人员提醒与快速添加、已关注人员激活 BUG 汇总、一键催办、周报生成 |
| **数据下载** | 勾选项目批量从禅道下载最新 BUG 数据（SSE 实时进度）、每次导入自动记录人员趋势快照 |
| **项目管理** | 添加/编辑/删除禅道项目 |
| **设置** | Cookie 配置与验证、缓存清理、定时自动下载开关与时间 |

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
│   │   ├── config_api.py# 配置读写
│   │   ├── export.py    # CSV 导出
│   │   ├── focus.py     # 关注人员
│   │   ├── import_api.py # 导入/批量下载
│   │   ├── projects.py  # 项目管理
│   │   └── trend.py     # 趋势数据 API
│   ├── services/        # 业务逻辑
│   │   ├── bug_analyzer.py
│   │   ├── config_store.py
│   │   ├── cookie_manager.py
│   │   ├── diff_engine.py
│   │   ├── file_reader.py
│   │   ├── export.py
│   │   ├── scheduler.py # 定时任务调度
│   │   └── trend_store.py # 趋势数据持久化
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

## 更新日志

### v3.4.0 (2026-05-18)
- UI 全面升级：暖骨色 monochrome 调色板、发丝级边框、Spring 缓动曲线、微阴影
- 更多过渡动效：骨架屏加载、卡片悬浮抬升、模态缩放淡入、按钮波纹
- 桌面快捷方式图标改为透明底深色虫子（含5尺寸 ICO）
- 重启服务改用 pythonw.exe 无窗口启动，消除多余 CMD 窗口
- 定时提醒/Cookie 警告关闭后服务端持久化，重启不再复现
- 邮件报告/周报移除"较上期"变化列
- AI 催办文案接入可配置 LLM（OpenAI/Anthropic 兼容）
- 修复 AI 生成中文案无换行的问题

### v3.3.0 (2026-05-12)
- PyWebView 桌面应用：原生窗口 + WebView2，单实例锁，控制台隐藏
- VBScript 无窗口启动器（启动.vbs）
- 忽略/确认记录服务端持久化（不受 WebView2 缓存影响）
- 关注人员匹配增加数字后缀歧义检测

### v3.2.0 (2026-05-08)
- 新增一键催办：支持单人/多人模式，预览后复制催办文案（含 BUG 详情与链接）
- 新增周报：本周汇总、环比变化、新增 BUG 清单，支持复制和下载
- 新增定时自动下载：APScheduler 每天定时串行下载所有关注项目数据
- 修复严重程度映射错误（禅道 1-4 值按 1-based 归一化）
- 修复项目切换时文件跨项目匹配串数据
- 修复定时任务并行下载导致 ZenTao 会话冲突（改为串行）
- 修复催办覆盖已关注人员总激活 BUG 计数（现同时显示总数与当前选中人）
- 修复关注人员弹窗列表排序：已关注人员优先显示
- 修复 /compare 和 POST /analyze 端点文件匹配错误（数字 ID 被误用作文件名前缀）
- 修复 CSV 导出忽略项目过滤（始终取全局最新文件而非当前项目）
- 调度器改为串行下载，避免并行导致 ZenTao 会话冲突

### v3.1.0 (2026-04-30)
- 新增 BUG 趋势折线图：每次导入后自动记录人员 BUG 快照，支持合计/单人视图切换
- 新增未关注人员快速添加：提醒横幅点击直接筛选新增人员，手动勾选合并到关注列表
- Chart.js 本地化：移除 CDN 和 Google Fonts 外部依赖，页面离线可用
- 数据分析页底部显示已关注人员激活 BUG 总数
- 修复关注弹窗搜索时勾选状态丢失
- 修复浏览器缓存导致趋势图按钮无响应
- 修复未关注提醒跨页面刷新持久化（sessionStorage 按项目存储）

### v3.0.0 (2026-04-28)
- 网页版重构：FastAPI + 原生 JS 全栈替代 PyQt6 GUI
- 多项目批量下载、SSE 实时进度、同比环比分析
