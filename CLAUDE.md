# Claude 工作指南

## 项目概述
Instagram 下载器：使用 Selenium + Instaloader 下载 IG 帖子，支持 Web UI、监控新帖子、Telegram 推送。

## 核心文件（优先阅读）
- `scraper.py` - 主下载逻辑
- `web_app.py` - Flask Web UI
- `monitor.py` - 新帖子监控
- `utils.py` - 浏览器/Cookie/重试工具
- `telegram_bot.py` - TG 推送
- `config.py` - 配置管理

## Token 节省规则

### 1. 文件读取策略
- **禁止读取**：`.venv/`、`downloads/`、`.cache/`、`.git/` 目录
- **按需读取**：只读取需要修改的文件，不要一次性读取所有文件
- **使用 Glob/Grep**：先用 Glob 定位文件，用 Grep 搜索关键代码，确认后再 Read

### 2. 代码修改原则
- **最小改动**：只修改必要的代码行，不重构无关代码
- **不添加注释**：除非用户明确要求，否则不添加文档字符串或注释
- **不优化代码**：不做性能优化、不添加错误处理（除非是 bug 修复）
- **使用 Edit 工具**：优先使用 Edit 而非 Write，只传输差异部分

### 3. 问题诊断流程
1. 先询问用户具体问题和错误信息
2. 使用 Grep 搜索相关代码片段
3. 只读取相关文件的必要部分（使用 offset/limit）
4. 提出修改方案，等待用户确认后再执行

### 4. 测试和验证
- **不自动运行测试**：除非用户明确要求
- **不启动服务**：不运行 `./web`、`python scraper.py` 等长时间运行的命令
- **语法检查**：修改后用 `python -m py_compile <file>` 快速验证语法

### 5. 响应风格
- **简洁回复**：直接说明修改内容，不重复用户的问题
- **无需总结**：完成任务后简单确认即可，不列出详细步骤
- **中文交流**：用户用中文提问时用中文回复

## 常见任务快速参考

### 修改下载逻辑
```bash
grep -n "def download" scraper.py  # 定位函数
# 然后只读取相关函数部分
```

### 修改 Web UI
- 前端：`templates/index.html`、`static/js/app.js`
- 后端：`web_app.py` 中的路由函数

### 修改监控逻辑
```bash
grep -n "check_new_posts" monitor.py
```

### 修改配置
- 用户配置：`config.yaml`（用户自定义）
- 配置解析：`config.py`

## 依赖信息
- Python 3.12
- 主要库：selenium, instaloader, flask, requests, pyyaml
- 虚拟环境：`.venv/`（已安装所有依赖）

## 注意事项
- Cookie 文件 `cookies.pkl` 包含敏感信息，不要读取或修改
- `tg_config.json` 包含 Telegram 配置，不要读取
- 下载目录 `downloads/` 可能很大，避免列出其内容
- Web 服务使用 gunicorn 运行，PID 文件：`gunicorn.pid`

## 用户偏好
- 余额有限，优先节省 token
- 直接修改代码，少问多做（在明确需求的情况下）
- 中文交流
