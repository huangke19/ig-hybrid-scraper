"""
Telegram 命令 Bot - 接收远程下载指令
支持命令：
  直接发送 IG 链接 - 下载帖子
  账号名 帖子序号 - 下载指定账号的第N条帖子（例如：username 3）
  /status - 查看运行状态
  /monitor - 立即检查新帖子
"""

import time
import re
import requests
from telegram_bot import load_tg_config, send_message
from scraper import download_selected_posts, fetch_post_urls_via_selenium
from monitor import monitor_once


def get_updates(token: str, offset: int = 0, timeout: int = 30):
    """长轮询获取新消息"""
    url = f"https://api.telegram.org/bot{token}/getUpdates"
    params = {"offset": offset, "timeout": timeout}
    try:
        resp = requests.get(url, params=params, timeout=timeout + 5)
        return resp.json() if resp.ok else None
    except Exception as e:
        print(f"❌ 获取消息失败: {e}")
        return None


def handle_command(token: str, chat_id: str, text: str):
    """处理命令"""
    text = text.strip()

    if text == "/status":
        send_message(token, chat_id, "✅ Bot 运行中")
        return

    if text == "/monitor":
        send_message(token, chat_id, "🔍 开始检查新帖子...")
        try:
            monitor_once()
        except Exception as e:
            send_message(token, chat_id, f"❌ 检查失败: {str(e)}")
        return

    # 检测是否是 IG 链接（支持多种格式）
    ig_pattern = r'(?:https?://)?(?:www\.)?instagram\.com/(?:p|reel)/[\w-]+'
    match = re.search(ig_pattern, text)

    if match:
        url = match.group(0)
        if not url.startswith('http'):
            url = 'https://' + url

        send_message(token, chat_id, f"🚀 开始下载")

        try:
            download_selected_posts(
                urls=[url],
                save_folder="downloads",
                tg_config=(token, chat_id),
                push_mode="each"
            )
            send_message(token, chat_id, f"✅ 下载完成")
        except Exception as e:
            send_message(token, chat_id, f"❌ 下载失败: {str(e)}")
        return

    # 检测格式：账号名 帖子序号
    parts = text.split()
    if len(parts) == 2 and parts[1].isdigit():
        username = parts[0]
        post_index = int(parts[1])

        if post_index < 1:
            send_message(token, chat_id, "❌ 帖子序号必须大于 0")
            return

        send_message(token, chat_id, f"🔍 正在获取 @{username} 的第 {post_index} 条帖子...")

        try:
            urls = fetch_post_urls_via_selenium(username, post_index)
            if len(urls) < post_index:
                send_message(token, chat_id, f"❌ 该账号只有 {len(urls)} 条帖子")
                return

            target_url = urls[post_index - 1]
            send_message(token, chat_id, f"🚀 开始下载")

            download_selected_posts(
                urls=[target_url],
                save_folder="downloads",
                tg_config=(token, chat_id),
                push_mode="each"
            )
            send_message(token, chat_id, f"✅ 下载完成")
        except Exception as e:
            send_message(token, chat_id, f"❌ 下载失败: {str(e)}")
        return

    if text.startswith("/"):
        send_message(token, chat_id,
            "可用命令:\n"
            "• 直接发送 IG 链接下载\n"
            "• 账号名 帖子序号（例如：username 3）\n"
            "/status - 查看状态\n"
            "/monitor - 检查新帖子"
        )


def run_bot():
    """启动 Bot 主循环"""
    config = load_tg_config()
    if not config:
        print("❌ 未找到 Telegram 配置，请先运行 python telegram_bot.py 配置")
        return

    token, chat_id = config
    print(f"🤖 Telegram Bot 启动中...")
    print(f"📱 Chat ID: {chat_id}")
    print(f"💡 直接发送 IG 链接即可下载")
    print(f"💡 发送 /monitor 检查新帖子")

    offset = 0

    while True:
        try:
            result = get_updates(token, offset)
            if not result or not result.get("ok"):
                time.sleep(3)
                continue

            for update in result.get("result", []):
                offset = update["update_id"] + 1

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
