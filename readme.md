# 📸 IG Scraper

**中文** | [English](#-ig-scraper-1)

一个基于 Selenium + Instaloader 的 Instagram 图片/视频下载工具，支持按范围精准下载指定账号的帖子。

---

## ✨ 功能特性

- 🔐 手动登录保存 Cookie，支持双重验证账号
- 📥 下载图片、视频（含 Reels）
- 🎯 三种下载模式：最新 N 条 / 指定范围 / 单条帖子
- 🔄 下载失败自动重试（指数退避）
- 🛡️ 防检测：屏蔽 `navigator.webdriver`、随机延时、模拟真人停顿
- ⚡ 高效去重，大量帖子场景下性能优化

---

## 📁 项目结构

```
ig_scraper/
├── auth.py        # 登录并保存 Cookie
├── scraper.py     # 主下载程序
├── utils.py       # 公共工具模块
├── cookies.pkl    # 登录后自动生成，勿上传
└── downloads/     # 下载内容保存目录，自动创建
```

---

## 🚀 快速开始

### 1. 安装依赖

```bash
pip install selenium webdriver-manager instaloader requests
```

### 2. 登录保存 Cookie

```bash
python auth.py
```

浏览器会自动打开 Instagram 登录页，完成登录（含双重验证）后，等首页 Feed 完全加载再按回车，Cookie 会自动保存到本地。

### 3. 运行下载器

```bash
python scraper.py
```

按照提示输入目标账号和下载范围即可：

```
请输入目标账号 ID（例如: nasa）: nasa

请选择下载范围：
  1. 下载最新的 N 条帖子
  2. 下载特定范围（第 M 到第 N 条）
  3. 下载单条帖子（输入 URL 或 shortcode）
```

下载内容保存在 `downloads/<账号名>/` 目录下。

---

## ⚠️ 注意事项

- `cookies.pkl` 包含登录凭证，请勿上传到公开仓库（已建议加入 `.gitignore`）
- 下载间隔已内置随机延时，请勿手动调快，避免触发封号
- Cookie 有效期有限，若提示登录失效请重新运行 `auth.py`
- 本工具仅供学习研究使用，请遵守 Instagram 服务条款

---

## 🔧 `.gitignore` 建议

```
cookies.pkl
downloads/
.venv/
__pycache__/
```

---
---

# 📸 IG Scraper

[中文](#-ig-scraper) | **English**

A Selenium + Instaloader powered Instagram media downloader. Precisely download photos and videos from any public account by range or individually.

---

## ✨ Features

- 🔐 Manual login with Cookie persistence — supports two-factor authentication
- 📥 Downloads photos, videos, and Reels
- 🎯 Three download modes: latest N posts / custom range / single post
- 🔄 Auto-retry on failure with exponential backoff
- 🛡️ Bot detection bypass: hides `navigator.webdriver`, randomized delays, human-like pauses
- ⚡ Set-based deduplication for fast performance on large profiles

---

## 📁 Project Structure

```
ig_scraper/
├── auth.py        # Login and save cookies
├── scraper.py     # Main downloader
├── utils.py       # Shared utilities
├── cookies.pkl    # Auto-generated after login — do not commit
└── downloads/     # Downloaded media — auto-created
```

---

## 🚀 Quick Start

### 1. Install Dependencies

```bash
pip install selenium webdriver-manager instaloader requests
```

### 2. Login & Save Cookies

```bash
python auth.py
```

A Chrome window will open the Instagram login page. Complete the login (including 2FA if prompted), wait until the home Feed has fully loaded, then press Enter. Cookies will be saved automatically.

### 3. Run the Downloader

```bash
python scraper.py
```

Follow the prompts to enter the target account and choose a download mode:

```
Enter target username (e.g. nasa): nasa

Select download mode:
  1. Download the latest N posts
  2. Download a specific range (e.g. post 3 to 8)
  3. Download a single post (URL or shortcode)
```

Downloaded files are saved to `downloads/<username>/`.

---

## ⚠️ Important Notes

- `cookies.pkl` contains your login credentials — **never commit it to a public repo** (add to `.gitignore`)
- Built-in random delays protect your account — do not reduce them
- Cookies expire over time; re-run `auth.py` if you see login errors
- This tool is intended for personal and educational use only. Please respect Instagram's Terms of Service.

---

## 🔧 Recommended `.gitignore`

```
cookies.pkl
downloads/
.venv/
__pycache__/
```
