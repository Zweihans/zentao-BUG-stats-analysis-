# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## 项目概述

禅道BUG数据分析工具，网页版（FastAPI + 原生 JS SPA），支持多项目 BUG 下载、按人员分组统计、严重级别筛选、关注人员管理、柱状图/饼状图/趋势折线图、一键催办（AI 文案生成）、周报生成、定时自动下载、全局关注人员池。

## 运行命令

```bash
cd D:\ai\test\zentao_bug_analysis

# 安装依赖
pip install fastapi uvicorn apscheduler playwright python-multipart python-dotenv requests
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
│   ├── config_api.py    # 配置读写（过期时间、定时开关、催办偏好）
│   ├── export.py        # CSV 导出（severity 转 S/A/B/C 标签）
│   ├── focus.py         # 关注人员读写 + 全局关注池导入/匹配
│   ├── import_api.py    # 禅道导入/批量下载（SSE 进度推送）
│   ├── projects.py      # 项目管理 CRUD
│   ├── trend.py         # 趋势数据 API
│   └── urge_api.py      # AI 催办文案生成（多风格 + 自定义提示词 + 降级模板）
├── services/            # 业务逻辑
│   ├── ai_client.py     # AI 客户端（OpenAI/Anthropic 兼容，读取 .env 配置）
│   ├── bug_analyzer.py  # 按人员分组统计（S/A/B/C 计数、激活/已解决/已关闭分类）
│   ├── config_store.py  # 应用配置持久化（.app_config.json）
│   ├── cookie_manager.py# Cookie 存储与验证（Playwright 资源 finally 清理）
│   ├── diff_engine.py   # 新旧 BUG 对比，标记 is_new
│   ├── exporter.py      # 报表导出逻辑
│   ├── file_reader.py   # xlsx/csv 解析（zipfile+XML 直接解析，含 inlineStr 支持）
│   ├── scheduler.py     # APScheduler 定时任务（串行下载 + 日志 5MB 轮转）
│   └── trend_store.py   # 趋势数据 upsert（按日期覆盖，线程安全）
└── stores/              # 数据持久化
    ├── focus_store.py   # 关注人员列表 + 全局关注池 + 中文姓名匹配
    └── project_store.py # 项目配置（import_projects.json）
static/
├── index.html           # SPA 入口（含催办/周报/重名确认等模态窗口）
├── css/style.css        # 样式（含 badge-overdue 延期徽标）
├── favicon.svg          # 网站图标
└── js/
    ├── api.js           # API 请求封装（含 FormData upload、EventSource SSE）
    ├── app.js           # 主逻辑：分析、图表、催办(AI)、周报、邮件报告、关注池
    ├── batch.js         # 批量下载页
    └── settings.js      # 项目管理/设置页
zentao_importer.py       # Playwright 禅道下载引擎
```

## 数据流向

```
禅道网页（Playwright 自动化）
    ↓ 导出 xlsx
downloads/ 目录
    ↓ file_reader.py 解析（含 openedDate / deadline）
bug_analyzer.py 按人员分组统计（含 is_new 标记）
    ↓
API JSON → 前端 app.js 渲染（含延期天数徽标）
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
- CSV 导出：使用 `severity_label()` 转换为 S/A/B/C 标签

### 新增 BUG 标记
- `diff_engine.py` 对比当天与前一天（或更早）的文件，标记新出现的 BUG ID
- 前端显示"新增"徽标（蓝色），延期显示"延期X天"徽标（红色）

### AI 催办文案
- 后端 `urge_api.py`：支持正式/口语化/简洁三种风格 + 用户自定义额外提示词
- 前端 `openUrgeModal()`：风格切换保存偏好但不自动重生成，通过"重新生成"按钮触发
- AI 不可用时自动降级为前端模板文案
- AI 配置通过 `ai_client.py` 读写 `.env` 文件，设置页可测试连接

### 周报
- 前端 `generateWeeklyHTML()`：复用邮件报告结构，增加环比变化 + 本周新增 BUG 清单
- 环比对比使用最后两条不同日期的趋势记录（同天多次导入不产生假环比）

### Cookie 管理
- Cookie 通过设置页手动输入并保存
- 所有 Playwright 浏览器实例共用同一 Cookie
- 定时任务串行下载避免会话冲突
- `verify_cookie()` 使用 try/finally 确保 Playwright 资源释放

### 调度器
- APScheduler AsyncIOScheduler，每天指定时间执行一次
- 单个 cron job 串行处理所有 `focus=true` 的项目
- `main.py` 使用 `reload=False` 保证单进程
- 调度日志 `logs/scheduler.log` 超过 5MB 自动轮转为 `.old`

### 全局关注人员池
- 上传飞书等导出的 Excel/CSV 文件，自动提取各 sheet 的"姓名"列
- 分析数据时自动匹配：确定匹配直接关注；前缀/重名弹出确认弹窗
- 中文姓名提取：正则 `[一-鿿]{2,4}`，去数字后缀，处理多片段前缀
- 重名确认弹窗支持持久化跳过（localStorage），避免反复弹出

### 前端持久化
- 未关注人员提醒：localStorage（关浏览器不丢失），仅 × 关闭时写入
- 重名确认跳过：localStorage，4 个关闭路径（×/跳过/确认/遮罩）均持久化
- AI 催办偏好（风格/自定义提示词）：服务端 `.app_config.json`

### 前端版本号
- 静态资源通过 `?v=3.6.0` 管理缓存，更新后在 index.html 中升级版本号

## 配置说明

### 关注列表
- 按项目 ID 存储：`{project_id}list.json`（如 `1list.json`, `2list.json`）
- 默认文件：`focus_list.json`
- `is_focused` 使用子串匹配（支持部分名称匹配）

### 全局关注池
- 文件：`focus_pool.json`
- 通过设置页上传 Excel/CSV 导入，自动合并去重

### 项目配置
- `import_projects.json`：项目名称、禅道 URL、focus 标记
- `.app_config.json`：过期时间、定时开关、定时小时、催办偏好

### AI 配置
- 文件：`.env`（项目根目录）
- 字段：`AI_BASE_URL`、`AI_API_KEY`、`AI_MODEL`
- API Key 明文存储，需注意文件权限

### 禅道 BUG 链接
`https://zd.bicv.com/bug-view-{bugID}.html`
