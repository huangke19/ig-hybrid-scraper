# IG 精准范围下载器

用 Selenium + Instaloader 下载 Instagram 帖子，支持下载后推送到 Telegram。

## 文件结构

```
ig_scraper/
├── auth.py           # 登录 & 初始化配置（首次运行）
├── scraper.py        # 主程序：下载 + 可选 Telegram 推送
├── utils.py          # 公共工具：浏览器、Cookie、重试、延时
├── telegram_bot.py   # Telegram 推送模块
├── cookies.pkl       # 登录后自动生成，勿手动修改
└── tg_config.json    # Telegram 配置，自动生成
```

## 安装依赖

```bash
pip install selenium webdriver-manager instaloader requests
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
python scraper.py
```

按提示选择下载范围：

| 选项 | 说明 |
|------|------|
| 1 | 下载最新 N 条帖子 |
| 2 | 下载第 M ~ 第 N 条帖子 |
| 3 | 下载单条（输入完整 URL 或 shortcode）|

下载完成后会询问是否推送到 Telegram，以及推送时机（实时 / 批量）。

下载文件保存在：`downloads/<账号名>/`

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
downloads/
.venv/
__pycache__/
```
