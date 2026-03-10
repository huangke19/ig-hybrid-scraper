# Instagram 下载器项目开发指南

> 本文档为 AI 助手快速上手项目而设计，包含完整的技术栈、架构设计、API 接口和开发约定。

## 项目概述

Instagram 下载器：使用 Selenium + Instaloader 下载 IG 帖子，支持 Web UI、监控新帖子、Telegram 推送。

**技术栈**：
- Python 3.12
- Selenium 4.41.0 + WebDriver Manager 4.0.2（浏览器自动化）
- Instaloader 4.15（Instagram API 封装）
- FastAPI 2.0（Web 服务，替代旧版 Flask）
- Requests 2.32.5（HTTP 请求）
- PyYAML 6.0.3（配置管理）
- Go 1.x（监控服务，独立二进制）

**虚拟环境**：`.venv/`（已安装所有依赖）

**代码规模**：约 2286 行 Python 代码

---

## 核心文件架构

### 1. 主程序模块（8 个 Python 文件）

#### `scraper.py` (23394 字节)
**核心下载逻辑**，包含 11 个函数：

- `load_downloaded_users()` - 加载下载历史用户列表
- `save_downloaded_user(username)` - 保存用户到历史记录
- `fetch_post_urls_via_api(target_user, required_count)` - 使用 Instaloader API 快速获取帖子链接（无浏览器）
- `fetch_post_urls_via_selenium(target_user, required_count)` - 用 Selenium 模拟滚动抓取链接（更隐蔽）
- `fetch_post_urls(target_user, required_count, use_cache=True)` - 统一入口，优先 API，失败回退 Selenium
- `_build_loader(save_folder)` - 构建 Instaloader 实例
- `_find_post_files(base_dir, shortcode)` - 查找已下载的帖子文件
- `_build_files_index(base_dir)` - 预扫描文件索引（性能优化）
- `_download_one(L, shortcode, save_folder)` - 下载单个帖子
- `_push_files(token, chat_id, files, shortcode)` - 推送文件到 Telegram
- `download_selected_posts(...)` - **主下载函数**，支持并发下载 + 进度回调
- `ask_telegram_push()` - 交互式询问是否推送
- `batch_download_mode(users)` - 批量下载多个用户
- `main()` - 命令行入口

**关键参数**：
```python
download_selected_posts(
    target_user: str,
    post_urls: list[str],
    enable_push: bool = False,
    push_mode: str = 'batch',  # 'each' | 'batch'
    max_workers: int = 3,       # 并发数
    progress_callback: callable = None  # 进度回调
)
```

#### `web_app_fastapi.py` (16367 字节)
**FastAPI Web 服务**，13 个路由：

**数据模型**（Pydantic）：
- `User`, `UsersResponse` - 用户列表
- `DownloadRequest`, `TaskResponse` - 下载任务
- `Task`, `TasksResponse` - 任务状态
- `TelegramConfig`, `TelegramConfigResponse` - TG 配置
- `BotStatusResponse`, `MessageResponse` - 通用响应
- `FolderInfo`, `FoldersResponse`, `FileInfo`, `FilesResponse` - 文件浏览

**API 路由**：
- `GET /` - 返回前端页面
- `GET /api/users` - 获取用户列表（favorite + history）
- `POST /api/download` - 启动下载任务（后台执行）
- `GET /api/tasks` - 获取所有任务状态
- `GET /api/tasks/{task_id}` - 获取单个任务详情
- `GET /api/config/telegram` - 获取 TG 配置状态
- `POST /api/config/telegram` - 保存 TG 配置
- `GET /api/bot/status` - 查询 Telegram Bot 运行状态
- `POST /api/bot/start` - 启动 Telegram Bot（后台进程）
- `POST /api/bot/stop` - 停止 Telegram Bot
- `GET /api/downloads` - 列出所有下载文件夹
- `GET /api/downloads/{username}` - 列出指定用户的文件
- `GET /downloads/{path:path}` - 下载文件

**全局变量**：
- `download_tasks: dict` - 任务状态字典
- `task_id_counter: int` - 任务 ID 计数器

#### `utils.py` (12841 字节)
**公共工具库**，12 个函数：

- `init_driver(headless=None)` - 初始化 Chrome WebDriver（防检测配置）
- `save_cookies(driver, path='cookies.pkl')` - 保存 Selenium Cookie
- `load_cookies_for_selenium(driver, path='cookies.pkl')` - 加载 Cookie 到 Selenium
- `load_cookies_for_requests(path='cookies.pkl')` - 转换 Cookie 为 Requests 格式
- `get_shortcode_from_url(url)` - 从 URL 提取 shortcode
- `retry(max_times=None, delay=None, backoff=1.5)` - 重试装饰器
- `human_sleep(min_sec=None, max_sec=None, long_pause_prob=None, ...)` - 人性化随机延时
- `load_json_file(filepath, default=None)` - 读取 JSON 文件
- `save_json_file(filepath, data)` - 保存 JSON 文件
- `save_urls_cache(username, urls)` - 缓存帖子链接
- `load_urls_cache(username)` - 读取缓存链接
- `clear_urls_cache(username)` - 清除缓存

**性能优化配置**（`init_driver`）：
- 禁用图片加载（节省 30-50% 时间）
- 禁用 GPU、扩展、通知
- 防检测参数（User-Agent、AutomationControlled）

#### `telegram_bot.py` (9657 字节)
**Telegram 推送模块**，11 个函数：

- `save_tg_config(bot_token, chat_id, path='tg_config.json')` - 保存配置
- `load_tg_config(path='tg_config.json')` - 读取配置
- `setup_tg_config()` - 交互式配置向导
- `_api_url(token, method)` - 构建 API URL
- `send_message(token, chat_id, text)` - 发送文本消息
- `_file_size_mb(path)` - 计算文件大小
- `send_photo(token, chat_id, photo_path, caption='')` - 发送图片
- `send_video(token, chat_id, video_path, caption='')` - 发送视频
- `send_media_group(token, chat_id, media_paths, caption='')` - 发送媒体组（最多 10 个）
- `push_post_folder(token, chat_id, folder_path, username, shortcode)` - 推送单个帖子文件夹
- `push_download_folder(token, chat_id, base_folder, username)` - 推送整个用户文件夹

**限制**：
- 单文件最大 50 MB
- 单次 `sendMediaGroup` 最多 10 个文件
- 支持格式：`.jpg`, `.jpeg`, `.png`, `.webp`, `.mp4`, `.mov`, `.avi`, `.mkv`

#### `config.py` (8323 字节)
**配置管理类**，1 个类：

```python
class Config:
    def __init__(self, config_path='config.yaml')
    def _load_config() -> dict
    def _default_config() -> dict
    def _merge_with_defaults(user_config) -> dict
    def get(section, key, default=None) -> Any
    def get_section(section) -> dict

    # 属性快捷访问
    @property
    def favorite_users() -> list[str]
    @property
    def browser_headless() -> bool
    @property
    def browser_user_agent() -> str
    @property
    def download_base_dir() -> str
    # ... 更多属性
```

**配置结构**（`config.yaml`）：
```yaml
favorite_users: [...]        # 常用用户列表
monitor_users: [...]         # 监控用户列表
browser:
  headless: true
  user_agent: "..."
download:
  base_dir: downloads
  save_metadata: false
  download_videos: true
  download_comments: false
  max_retries: 3
  retry_delay: 10
behavior:
  scroll_pause_min: 2.0
  scroll_pause_max: 3.5
  human_delay_min: 4.0
  human_delay_max: 8.0
  long_pause_prob: 0.1
  long_pause_min: 15.0
  long_pause_max: 30.0
telegram:
  enabled: false
  bot_token: ''
  chat_id: ''
  push_mode: batch  # each | batch | none
cookies:
  path: cookies.pkl
web:
  host: 0.0.0.0
  port: 5000
  api_token: ''
```

#### `auth.py` (2873 字节)
**登录认证模块**，2 个函数：

- `login_and_save(cookie_path='cookies.pkl')` - 打开浏览器手动登录并保存 Cookie
- `setup_telegram_optional()` - 可选配置 Telegram Bot

**使用流程**：
1. 运行 `python auth.py`
2. 在弹出的浏览器中登录 Instagram
3. 回车保存 Cookie
4. 可选配置 Telegram Bot

#### `telegram_command_bot_standalone.py` (5357 字节)
**Telegram 命令 Bot**（独立进程），3 个函数：

- `handle_message(update, context)` - 处理消息（IG 链接 / 用户名+序号）
- `handle_status(update, context)` - `/status` 命令
- `main()` - Bot 主循环

**支持命令**：
- 直接发送 IG 链接 → 自动下载
- `username 3` → 下载该用户第 3 条帖子
- `/status` → 查看 Bot 状态

#### `convert_cookies.py` (1038 字节)
**Cookie 格式转换工具**，将 `cookies.pkl` 转换为 `cookies.json`。

---

### 2. 前端文件

#### `templates/index.html`
**Web UI 主页面**，包含 3 个 Tab：
- 下载管理（创建任务、查看进度）
- 配置管理（Telegram Bot 配置、启停）
- 文件浏览（查看已下载文件）

#### `static/js/app.js`
**前端逻辑**，主要函数：
- `loadUsers()` - 加载用户列表
- `loadTasks()` - 加载任务列表（轮询刷新）
- `startDownload()` - 提交下载任务
- `loadTelegramConfig()` - 加载 TG 配置
- `saveTelegramConfig()` - 保存 TG 配置
- `startBot()` / `stopBot()` - 控制 Bot
- `loadFiles()` - 加载文件列表

#### `static/css/style.css`
**样式文件**

---

### 3. 启动脚本

#### `ig` (7785 字节)
**统一命令入口**（Bash 脚本）：

```bash
./ig run              # 运行单次下载
./ig web              # 启动 Web UI（后台）
./ig web stop         # 停止 Web UI
./ig web restart      # 重启 Web UI
./ig bot              # 启动 Telegram Bot（后台）
./ig bot stop         # 停止 Telegram Bot
./ig bot restart      # 重启 Telegram Bot
./ig status           # 查看所有服务状态
```

**管理的服务**：
- FastAPI Web UI（uvicorn，PID 文件：`uvicorn.pid`）
- Telegram Bot API（PID 文件：`telegram_bot_api.pid`）
- Go 监控服务（PID 文件：`monitor.pid`）

---

### 4. 监控服务

#### `monitor_go/ig_monitor` (14.9 MB 二进制)
**Go 编写的监控服务**，每 24 小时检查一次新帖子。

**源码**：`monitor_go/main.go` (6571 字节)

**状态文件**：`monitor_state.json`
```json
{
  "username": {
    "last_check": "2026-03-10T12:00:00Z",
    "latest_shortcode": "ABC123"
  }
}
```

**日志文件**：`monitor_go.log`

---

## 数据文件

### 敏感文件（禁止读取/修改）
- `cookies.pkl` - Instagram Cookie（Pickle 格式）
- `cookies.json` - Instagram Cookie（JSON 格式）
- `tg_config.json` - Telegram 配置
- `data/tg_config.json` - Telegram 配置备份

### 自动生成文件
- `downloaded_users.json` - 下载历史用户列表
- `data/downloaded_users.json` - 下载历史备份
- `monitor_state.json` - 监控状态
- `data/monitor_history.json` - 监控历史
- `.cache/<username>_posts.json` - 帖子链接缓存
- `data/.cache/<username>_posts.json` - 缓存备份

### 日志文件
- `web_app.log` - Web 服务日志
- `fastapi.log` - FastAPI 日志
- `telegram_bot.log` - Bot 日志
- `telegram_bot_api.log` - Bot API 日志
- `monitor_go.log` - 监控日志
- `monitor.log` / `monitor.error.log` - 旧版监控日志

### PID 文件
- `uvicorn.pid` - Web 服务进程 ID
- `telegram_bot.pid` - Bot 进程 ID
- `telegram_bot_api.pid` - Bot API 进程 ID
- `monitor.pid` - 监控进程 ID

### 下载目录
- `downloads/<username>/` - 用户下载文件夹
  - 文件命名：`<date>_<shortcode>_<index>.<ext>`
  - 示例：`2026-03-10_ABC123_1.jpg`

---

## 开发约定

### Token 节省规则

#### 1. 文件读取策略
- **禁止读取**：`.venv/`, `downloads/`, `.cache/`, `.git/`, `data/` 目录
- **按需读取**：只读取需要修改的文件，不要一次性读取所有文件
- **使用 Glob/Grep**：先用 Glob 定位文件，用 Grep 搜索关键代码，确认后再 Read
- **分段读取**：大文件使用 `offset`/`limit` 参数只读相关部分

#### 2. 代码修改原则
- **最小改动**：只修改必要的代码行，不重构无关代码
- **不添加注释**：除非用户明确要求，否则不添加文档字符串或注释
- **不优化代码**：不做性能优化、不添加错误处理（除非是 bug 修复）
- **使用 Edit 工具**：优先使用 Edit 而非 Write，只传输差异部分
- **不自动提交**：修改代码后不自动运行 git commit，除非用户明确要求

#### 3. 问题诊断流程
1. 先询问用户具体问题和错误信息
2. 使用 Grep 搜索相关代码片段
3. 只读取相关文件的必要部分（使用 offset/limit）
4. 提出修改方案，等待用户确认后再执行

#### 4. 测试和验证
- **不自动运行测试**：除非用户明确要求
- **不启动服务**：不运行 `./ig web`、`python scraper.py` 等长时间运行的命令
- **语法检查**：修改后用 `python -m py_compile <file>` 快速验证语法

#### 5. 响应风格
- **简洁回复**：直接说明修改内容，不重复用户的问题
- **无需总结**：完成任务后简单确认即可，不列出详细步骤
- **中文交流**：用户用中文提问时用中文回复

### 代码风格

- **类型注解**：使用 Python 3.12+ 类型注解（`list[str]`, `dict[str, Any]`）
- **函数文档**：简洁的单行或多行文档字符串
- **错误处理**：使用 `try-except` 捕获异常，记录日志
- **日志记录**：使用 `logging` 模块，级别：INFO（正常）、WARNING（警告）、ERROR（错误）
- **命名规范**：
  - 函数/变量：`snake_case`
  - 类：`PascalCase`
  - 常量：`UPPER_CASE`
  - 私有函数：`_leading_underscore`

### Git 提交规范

- **提交信息**：中文，简洁描述改动内容
- **示例**：
  - `优化下载速度：并发下载 + 大幅缩短延迟`
  - `用 Go 重写监控功能，替换 Rust 版本`
  - `删除 Flask 旧版本，统一使用 FastAPI`

---

## 常见任务快速参考

### 修改下载逻辑
```bash
# 定位主下载函数
grep -n "def download_selected_posts" scraper.py
# 输出：296:def download_selected_posts(

# 定位获取链接函数
grep -n "def fetch_post_urls" scraper.py
# 输出：165:def fetch_post_urls(
```

### 修改 Web API
```bash
# 查找所有路由
grep -n "@app\." web_app_fastapi.py

# 修改下载接口
# 文件：web_app_fastapi.py
# 行号：167 (@app.post('/api/download'))
```

### 修改前端逻辑
- 前端页面：`templates/index.html`
- 前端脚本：`static/js/app.js`
- 样式文件：`static/css/style.css`

### 修改配置
- 用户配置：`config.yaml`（用户自定义）
- 配置解析：`config.py`（代码逻辑）

### 修改工具函数
```bash
# 查找所有工具函数
grep -n "^def " utils.py

# 常用函数位置
# init_driver: 34
# save_cookies: 103
# load_cookies_for_selenium: 110
# load_cookies_for_requests: 141
# retry: 190
# human_sleep: 230
```

---

## 依赖信息

### Python 依赖（requirements.txt）
```
selenium==4.41.0
webdriver-manager==4.0.2
instaloader==4.15
requests==2.32.5
PyYAML==6.0.3
```

### 运行时依赖
- Chrome 浏览器（Selenium 需要）
- ChromeDriver（自动下载管理）

---

## 注意事项

### 安全性
- Cookie 文件包含敏感信息，不要读取或修改
- `tg_config.json` 包含 Telegram 配置，不要读取
- 下载目录 `downloads/` 可能很大，避免列出其内容

### 性能
- Selenium 初始化较慢，优先使用 Instaloader API
- 并发下载默认 3 个线程，可通过 `max_workers` 参数调整
- 禁用图片加载可节省 30-50% 时间

### 常见问题
- Cookie 过期会导致下载失败 → 重新运行 `python auth.py`
- Selenium 需要 Chrome 版本匹配 ChromeDriver → 自动管理
- 网络超时是常见问题 → 使用 `@retry` 装饰器

---

## 维护约定

**重要**：每次对话完成功能后，自动将本次新增的内容更新到本文档，无需用户提醒。

### 更新内容包括：
1. **新增文件**：文件路径、用途、关键函数
2. **API 接口**：新增路由、请求/响应格式
3. **配置项**：新增配置字段、默认值
4. **重要决策**：架构变更、技术选型、性能优化

### 更新格式：
在对应章节末尾追加，格式如下：

```markdown
#### `新文件.py` (文件大小)
**功能描述**，包含 N 个函数：

- `function_name(params)` - 功能说明
- ...

**关键参数**：
\```python
function_name(
    param1: type,
    param2: type = default
)
\```

**更新时间**：2026-03-10
**更新原因**：简要说明为什么新增此功能
```

### 示例更新记录：

#### 更新历史

**2026-03-10**：
- 删除 Flask 旧版本（`web_app.py`），统一使用 FastAPI（`web_app_fastapi.py`）
- 用 Go 重写监控功能（`monitor_go/`），替换 Rust 版本
- 优化下载速度：并发下载 + 大幅缩短延迟（`scraper.py:296`）

---

## 快速上手检查清单

新对话开始时，确认以下内容：

- [ ] 已读取本文档（`CLAUDE.md`）
- [ ] 了解项目技术栈（Python 3.12 + Selenium + Instaloader + FastAPI）
- [ ] 知道核心文件位置（`scraper.py`, `web_app_fastapi.py`, `utils.py`）
- [ ] 理解 Token 节省规则（按需读取、最小改动、使用 Grep/Glob）
- [ ] 知道敏感文件列表（`cookies.pkl`, `tg_config.json`）
- [ ] 了解启动命令（`./ig web`, `./ig bot`, `./ig status`）

**准备就绪，开始开发！**
