"""
Telegram 命令 Bot (API 版本) - 通过 FastAPI 接口下载
支持命令：
  直接发送 IG 链接 - 下载帖子
  账号名 帖子序号 - 下载指定账号的第N条帖子（例如：username 3）
  /status - 查看运行状态
"""

import time
import re
import requests
from telegram_bot import load_tg_config, send_message

API_BASE = "http://localhost:8000"


def get_updates(token: str, offset: int = 0, timeout: int = 30):
    """长轮询获取新消息"""
    url = f"https://api.telegram.org/bot{token}/getUpdates"
    params = {"offset": offset, "timeout": timeout}
    try:
        print(f"⏳ 等待新消息... (offset={offset})")
        resp = requests.get(url, params=params, timeout=timeout + 5)
        return resp.json() if resp.ok else None
    except Exception as e:
        print(f"❌ 获取消息失败: {e}")
        return None


def call_api(endpoint: str, method: str = "GET", data: dict = None):
    """调用 FastAPI 接口"""
    url = f"{API_BASE}{endpoint}"
    try:
        if method == "GET":
            resp = requests.get(url, timeout=10)
        else:
            resp = requests.post(url, json=data, timeout=10)

        if resp.ok:
            return resp.json()
        else:
            print(f"❌ API 调用失败: {resp.status_code} - {resp.text}")
            return None
    except Exception as e:
        print(f"❌ API 调用异常: {e}")
        return None


def handle_command(token: str, chat_id: str, text: str):
    """处理命令"""
    text = text.strip()

    if text == "/status":
        result = call_api("/api/tasks")
        if result:
            tasks = result.get("tasks", [])
            running = [t for t in tasks if t["status"] == "running"]
            completed = [t for t in tasks if t["status"] == "completed"]
            msg = f"✅ Bot 运行中\n📊 任务统计:\n• 运行中: {len(running)}\n• 已完成: {len(completed)}\n• 总计: {len(tasks)}"
            send_message(token, chat_id, msg)
        else:
            send_message(token, chat_id, "✅ Bot 运行中（API 连接失败）")
        return

    # 检测是否是 IG 链接
    ig_pattern = r'(?:https?://)?(?:www\.)?instagram\.com/(?:p|reel)/[\w-]+'
    match = re.search(ig_pattern, text)

    if match:
        url = match.group(0)
        if not url.startswith('http'):
            url = 'https://' + url

        print(f"🔽 开始下载: {url}")
        send_message(token, chat_id, f"🔽 开始下载: {url}")

        result = call_api("/api/download", "POST", {
            "username": "",
            "type": "single",
            "url": url,
            "enable_push": True
        })

        if result:
            task_id = result.get("task_id")
            print(f"✅ 任务已创建: {task_id}")
            send_message(token, chat_id, f"✅ 任务已创建，正在后台下载...")
        else:
            send_message(token, chat_id, "❌ 创建任务失败，请检查 API 服务")
        return

    # 检测格式：账号名 帖子序号
    parts = text.split()
    if len(parts) == 2 and parts[1].isdigit():
        username = parts[0]
        post_index = int(parts[1])

        if post_index < 1:
            send_message(token, chat_id, "❌ 帖子序号必须大于 0")
            return

        print(f"🔽 下载 @{username} 的第 {post_index} 条帖子")
        send_message(token, chat_id, f"🔽 正在下载 @{username} 的第 {post_index} 条帖子...")

        result = call_api("/api/download", "POST", {
            "username": username,
            "type": "index",
            "index": post_index,
            "enable_push": True
        })

        if result:
            task_id = result.get("task_id")
            print(f"✅ 任务已创建: {task_id}")
            send_message(token, chat_id, f"✅ 任务已创建，正在后台下载...")
        else:
            send_message(token, chat_id, "❌ 创建任务失败，请检查 API 服务")
        return

    if text.startswith("/"):
        send_message(token, chat_id,
            "可用命令:\n"
            "• 直接发送 IG 链接下载\n"
            "• 账号名 帖子序号（例如：username 3）\n"
            "/status - 查看状态"
        )


def run_bot():
    """启动 Bot 主循环"""
    config = load_tg_config()
    if not config:
        print("❌ 未找到 Telegram 配置，请先运行 python telegram_bot.py 配置")
        return

    token, chat_id = config
    print(f"🤖 Telegram Bot 启动中 (API 版本)...")
    print(f"📱 Chat ID: {chat_id}")
    print(f"🌐 API 地址: {API_BASE}")
    print(f"💡 直接发送 IG 链接即可下载")

    # 测试 API 连接
    result = call_api("/api/tasks")
    if result:
        print(f"✅ API 连接成功")
    else:
        print(f"⚠️  API 连接失败，请确保 FastAPI 服务已启动")

    offset = 0

    while True:
        try:
            result = get_updates(token, offset)
            if not result or not result.get("ok"):
                time.sleep(3)
                continue

            updates = result.get("result", [])
            if not updates:
                continue

            offset = updates[-1]["update_id"] + 1

            for update in updates:
                message = update.get("message", {})
                msg_chat_id = str(message.get("chat", {}).get("id", ""))
                msg_text = message.get("text", "")

                if msg_chat_id != chat_id:
                    continue

                if msg_text:
                    print(f"📩 收到消息: {msg_text}")
                    handle_command(token, chat_id, msg_text)

        except KeyboardInterrupt:
            print("\n👋 Bot 已停止")
            break
        except Exception as e:
            print(f"❌ 错误: {e}")
            time.sleep(5)


if __name__ == "__main__":
    run_bot()
