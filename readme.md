# IG 精准范围下载器

用 Selenium + Instaloader 下载 Instagram 帖子，支持下载后推送到 Telegram。

## 文件结构

```
ig_scraper/
├── auth.py              # 登录 & 初始化配置（首次运行）
├── scraper.py           # 主程序：下载 + 可选 Telegram 推送
├── monitor.py           # 监控脚本：自动检测新帖子并推送通知
├── utils.py             # 公共工具：浏览器、Cookie、重试、延时
├── telegram_bot.py      # Telegram 推送模块
├── config.py            # 配置文件管理模块
├── config.yaml          # 配置文件（可选，复制 config.yaml.example 修改）
├── config.yaml.example  # 配置文件示例
├── run                  # 快速启动脚本（自动激活虚拟环境）
├── monitor              # 监控脚本启动器
├── com.ig.monitor.plist # macOS launchd 配置文件
├── MONITOR.md           # 监控功能详细说明
├── cookies.pkl          # 登录后自动生成，勿手动修改
├── tg_config.json       # Telegram 配置，自动生成
├── downloaded_users.json # 下载历史用户列表，自动生成
└── .cache/              # 链接缓存目录，自动生成
```

## 安装依赖

```bash
pip install selenium webdriver-manager instaloader requests pyyaml
```

## 快速开始

### 第一步：初始化（只需做一次）

```bash
python auth.py
```

程序会：
1. 弹出 Chrome 浏览器 → 手动完成 Instagram 登录 → 回车保存 Cookie
2. 询问是否配置 Telegram Bot（可跳过，之后运行 scraper.py 时也可配置）

### 第二步：运行下载器

```bash
./run
```

或者：

```bash
python scraper.py
```

按提示选择下载范围：

| 选项 | 说明 |
|------|------|
| 1 | 下载最新 N 条帖子 |
| 2 | 下载第 M ~ 第 N 条帖子 |
| 3 | 下载指定第几条帖子 |
| 4 | 下载单条（输入完整 URL 或 shortcode）|

下载完成后会询问是否推送到 Telegram，以及推送时机（实时 / 批量）。

下载文件保存在：`downloads/<账号名>/`

### 功能特性

- **用户列表管理**：自动记录下载过的用户，下次运行时显示在选项中
  - ⭐ 常用用户（在 `config.yaml` 中配置）
  - 📥 历史用户（自动记录到 `downloaded_users.json`）
- **链接缓存**：首次获取的帖子链接会缓存到 `.cache/` 目录，避免重复获取
- **断点续传**：已下载的文件会自动跳过，支持中断后继续下载
- **性能优化**：预扫描文件索引，减少磁盘 I/O 操作
- **批量下载**：支持一次性下载多个用户的内容
- **新帖子监控**：自动检测用户发布新帖子，通过 Telegram 推送通知（详见 [MONITOR.md](MONITOR.md)）

---

## 新帖子监控（可选）

如果你想自动监控用户发布新帖子并收到 Telegram 通知，可以使用监控功能。

### 快速开始

```bash
# 测试一次（推荐先测试）
python monitor.py --once

# 持续运行（每 24 小时检查一次）
./monitor

# 或者配置 macOS 自动运行（推荐）
cp com.ig.monitor.plist ~/Library/LaunchAgents/
launchctl load ~/Library/LaunchAgents/com.ig.monitor.plist
```

详细说明请查看 [MONITOR.md](MONITOR.md)

---

## 配置文件（可选）

你可以通过 `config.yaml` 配置文件来管理所有设置，避免每次运行时重复输入。

### 创建配置文件

```bash
cp config.yaml.example config.yaml
```

然后编辑 `config.yaml`，根据需要修改配置项。配置文件已包含详细的中文注释。

### 配置项说明

#### 浏览器设置 (browser)
- `headless`: 是否使用无头模式（不显示浏览器窗口）
  - `false`: 显示浏览器窗口，适合本地调试
  - `true`: 无头模式，适合服务器环境
- `user_agent`: 浏览器 User-Agent，用于伪装成真实浏览器

#### 下载设置 (download)
- `base_dir`: 下载文件保存的基础目录（默认 `downloads`）
- `save_metadata`: 是否保存帖子元数据（JSON 格式，包含点赞数、评论数等）
- `download_videos`: 是否下载视频（设为 `false` 则只下载图片）
- `download_comments`: 是否下载评论（会显著增加时间）
- `max_retries`: 下载失败时的最大重试次数
- `retry_delay`: 重试前的等待时间（秒），每次重试会按 1.5 倍递增

#### 行为模拟设置 (behavior)
用于防止被检测为机器人：
- `scroll_pause_min/max`: 滚动页面时的暂停时间范围（秒）
- `human_delay_min/max`: 下载每个帖子之间的延时范围（秒）
- `long_pause_prob`: 长暂停的触发概率（0-1，0.1 表示 10%）
- `long_pause_min/max`: 长暂停的时间范围（秒），模拟真人停下来查看内容

#### Telegram 推送设置 (telegram)
- `enabled`: 是否启用 Telegram 推送
  - 设为 `true` 且填写了 token 和 chat_id 后，会自动推送，不再询问
- `bot_token`: Telegram Bot Token（从 @BotFather 获取）
- `chat_id`: Telegram Chat ID（从 @userinfobot 获取）
- `push_mode`: 推送模式
  - `each`: 每条下载完立即推送（实时）
  - `batch`: 全部下载完成后统一推送（推荐）
  - `none`: 不推送

#### Cookie 设置 (cookies)
- `path`: Cookie 文件路径（首次运行 `auth.py` 后自动生成）

#### 常用用户列表 (favorite_users)
在配置文件中添加常用用户列表，运行时会优先显示：

```yaml
favorite_users:
  - user1
  - user2
  - user3
```

这些用户会在选项中标记为 ⭐（常用用户）。

### 配置优先级

1. 如果存在 `config.yaml`，程序会优先使用配置文件中的设置
2. 配置文件中未设置的项会使用默认值
3. Telegram 设置：配置文件优先级高于交互式输入

---

## Telegram 推送配置

### 获取 Bot Token

1. 在 Telegram 搜索 `@BotFather`
2. 发送 `/newbot`，按提示创建 Bot
3. 创建完成后会收到 Token，格式如：`123456789:ABCdefGhIJKlmNoPQRsTUVwxyz`

### 获取 Chat ID

| 场景 | 方法 |
|------|------|
| 个人 | 搜索 `@userinfobot`，发任意消息即可获取 |
| 群组 / 频道 | 将 Bot 设为管理员，Chat ID 格式为负数或 `@频道名` |

> ⚠️ 配置完成后需先在 Telegram 向 Bot 发送一条 `/start`，否则 Bot 无法主动发消息。

### 推送时机说明

| 模式 | 说明 | 适合场景 |
|------|------|----------|
| 实时推送 | 每条下载完立即发送 | 下载数量少，想即时查看 |
| 批量推送 | 全部下载完成后统一发送 | 下载数量多，不想频繁通知 |

---

## 注意事项

- Cookie 有效期通常为数周，失效后重新运行 `auth.py` 登录即可
- 单个文件超过 50MB 时 Telegram 会自动跳过（Bot API 限制）
- 程序内置随机延时模拟真人行为，请勿同时开多个进程
- `cookies.pkl` 和 `tg_config.json` 包含敏感信息，已加入 `.gitignore`

## .gitignore 建议

```
cookies.pkl
tg_config.json
config.yaml
downloaded_users.json
urls_cache.json
.cache/
downloads/
.venv/
__pycache__/
```
