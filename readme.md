
---

# 📸 Instagram Hybrid Scraper (Selenium + Instaloader)

这是一个结合了 **Selenium** 模拟行为与 **Instaloader** 静态下载优势的 Instagram 爬虫工具。

### 🌟 核心优势

* **突破 429 限制**：通过模拟真人浏览器操作提取链接，有效规避 Instagram 严厉的 API 频率限制。
* **精准范围下载**：支持下载“前 $N$ 条”或“第 $A$ 到 $B$ 条”帖子，避免全量下载带来的封号风险。
* **高清原图/视频**：直接从 CDN 获取原始画质，支持多图贴（Carousel）和视频。
* **Session 保持**：只需登录一次，后续自动复用 Cookie。

---

## 🛠️ 环境要求

* **Python**: 3.8+
* **浏览器**: Google Chrome (及配套的 WebDriver)
* **依赖库**:
```bash
pip install selenium instaloader requests webdriver-manager

```



---

## 🚀 快速开始

项目由两个核心文件组成：授权模块 `auth.py` 和 抓取模块 `scraper.py`。

### 第一步：获取登录授权

运行 `auth.py` 以保存你的登录状态。

```bash
python auth.py

```

* 浏览器会自动打开 Instagram 登录页。
* **手动输入** 账号密码并完成登录（包括验证码）。
* 看到首页后，回到终端按 **回车**。
* 项目根目录将生成 `cookies.pkl`。

### 第二步：执行抓取

运行 `scraper.py`，根据提示进行交互：

```bash
python scraper.py

```

1. **输入目标 ID**: 比如 `jadeuly713`。
2. **选择下载模式**:
* **1**: 下载最新的 $N$ 条（如：下载前 5 条）。
* **2**: 下载指定范围（如：下载第 3 条到第 8 条）。
* **3**: 下载单条特定帖子（粘贴完整 URL）。



---

## 📂 项目结构

```text
ig_scraper/
├── auth.py           # 登录授权，生成 cookies.pkl
├── scraper.py        # 核心逻辑：链接提取 + 批量下载
├── .gitignore        # 忽略隐私数据上传（必须配置）
├── README.md         # 项目说明文档
└── downloads/        # (自动生成) 媒体文件存放目录

```

---

## ⚠️ 反爬避坑守则

* **适度下载**：建议单次任务不超过 30 篇，每天总量控制在 200 篇以内。
* **随机延迟**：脚本已内置 `8-15` 秒的随机冷却，请勿为了速度修改此参数。
* **隐私安全**：**切勿将 `cookies.pkl` 推送到 GitHub**。你的 `.gitignore` 应包含该文件。
* **冷却机制**：每下载 5 篇帖子，脚本会自动进行一次 60 秒以上的“深度休息”。

---

## 📄 免责声明

本项目仅供学习研究使用。请尊重 Instagram 社区准则及创作者版权。严禁将本项目用于任何商业用途或侵权行为。

---

### 💡 建议操作：添加 `requirements.txt`

为了让 GitHub 上的其他人更方便安装环境，建议你在终端运行：

```bash
pip freeze > requirements.txt

```

然后把这个 `requirements.txt` 也推送到 GitHub，别人只需运行 `pip install -r requirements.txt` 就能配置好环境。

**现在就把这份 README 推送到 GitHub 吧：**

```bash
git add README.md
git commit -m "docs: 完善项目说明文档"
git push

```