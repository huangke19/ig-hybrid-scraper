"""
monitor.py - IG 新帖子监控脚本
每天定时检查常用用户是否发布新帖子，有新帖子时推送 Telegram 通知
"""

import json
import time
from datetime import datetime
from pathlib import Path

from utils import get_shortcode_from_url
from scraper import fetch_post_urls
from telegram_bot import send_message, load_tg_config

try:
    from config import Config
    config = Config()
except ImportError:
    config = None


# ─────────────────────────────────────────────
# 用户历史管理
# ─────────────────────────────────────────────

HISTORY_FILE = "monitor_history.json"


def load_monitor_history() -> dict:
    """
    加载监控历史记录
    格式: {
        "user1": {
            "last_check_time": "2026-03-08 10:30:00",
            "last_shortcode": "ABC123xyz",
            "total_posts": 50
        }
    }
    """
    try:
        with open(HISTORY_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except FileNotFoundError:
        return {}
    except json.JSONDecodeError:
        return {}


def save_monitor_history(history: dict) -> None:
    """保存监控历史记录"""
    with open(HISTORY_FILE, "w", encoding="utf-8") as f:
        json.dump(history, f, ensure_ascii=False, indent=2)


def update_user_history(username: str, latest_shortcode: str) -> None:
    """更新用户的监控历史"""
    history = load_monitor_history()
    history[username] = {
        "last_check_time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "last_shortcode": latest_shortcode,
    }
    save_monitor_history(history)


# ─────────────────────────────────────────────
# 新帖子检测
# ─────────────────────────────────────────────

def check_new_posts(username: str) -> tuple[int, str | None]:
    """
    检测用户有多少条新帖子
    返回: (新帖子数量, 最新帖子的shortcode)
    """
    history = load_monitor_history()
    user_history = history.get(username)

    try:
        # 获取最新 20 条链接（不使用缓存，确保是最新的）
        print(f"  🔍 检查 @{username} 的新帖子...")
        recent_urls = fetch_post_urls(username, 20, use_cache=False)

        if not recent_urls:
            print(f"  ⚠️  无法获取 @{username} 的帖子列表")
            return 0, None

        # 获取最新帖子的 shortcode
        latest_shortcode = get_shortcode_from_url(recent_urls[0])

        # 如果是第一次检查这个用户
        if not user_history:
            print(f"  ℹ️  首次监控 @{username}，记录当前状态")
            update_user_history(username, latest_shortcode)
            return 0, latest_shortcode

        # 对比上次记录的 shortcode
        last_shortcode = user_history.get("last_shortcode")
        if not last_shortcode:
            update_user_history(username, latest_shortcode)
            return 0, latest_shortcode

        # 如果最新帖子和上次一样，说明没有新帖子
        if latest_shortcode == last_shortcode:
            print(f"  ✅ @{username} 没有新帖子")
            return 0, latest_shortcode

        # 找到上次记录的帖子在列表中的位置
        for i, url in enumerate(recent_urls):
            if get_shortcode_from_url(url) == last_shortcode:
                new_count = i
                print(f"  🆕 @{username} 有 {new_count} 条新帖子！")
                return new_count, latest_shortcode

        # 如果在前 20 条中找不到上次的帖子，说明有超过 20 条新帖子
        print(f"  🆕 @{username} 有超过 20 条新帖子！")
        return 20, latest_shortcode

    except Exception as e:
        print(f"  ❌ 检查 @{username} 时出错: {e}")
        return 0, None


# ─────────────────────────────────────────────
# 监控主逻辑
# ─────────────────────────────────────────────

def monitor_once() -> None:
    """执行一次监控检查"""
    print("\n" + "=" * 50)
    print(f"  📡 开始监控检查 - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 50)

    # 获取要监控的用户列表
    favorite_users = config.favorite_users if config else []

    if not favorite_users:
        print("\n⚠️  未配置常用用户列表，请在 config.yaml 中添加 favorite_users")
        return

    print(f"\n监控用户列表: {', '.join(favorite_users)}")

    # 加载 Telegram 配置
    tg_config = load_tg_config()
    if not tg_config:
        print("\n⚠️  未配置 Telegram，无法发送通知")
        print("请运行 python auth.py 配置 Telegram Bot")
        return

    token, chat_id = tg_config

    # 检查每个用户
    notifications = []
    for username in favorite_users:
        new_count, latest_shortcode = check_new_posts(username)

        if new_count > 0:
            notifications.append(f"• @{username}: {new_count} 条新帖子")
            # 更新历史记录
            if latest_shortcode:
                update_user_history(username, latest_shortcode)

        # 避免请求过快
        time.sleep(2)

    # 发送通知
    if notifications:
        message = "🆕 <b>Instagram 新帖子提醒</b>\n\n" + "\n".join(notifications)
        message += f"\n\n⏰ {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"

        print(f"\n📤 发送 Telegram 通知...")
        if send_message(token, chat_id, message):
            print("  ✅ 通知发送成功")
        else:
            print("  ❌ 通知发送失败")
    else:
        print("\n✅ 所有用户都没有新帖子")

    print("\n" + "=" * 50)
    print("  ✨ 监控检查完成")
    print("=" * 50)


def monitor_loop(interval_hours: int = 24) -> None:
    """
    持续监控循环
    interval_hours: 检查间隔（小时）
    """
    print("\n🚀 IG 新帖子监控已启动")
    print(f"⏰ 检查间隔: 每 {interval_hours} 小时")
    print("按 Ctrl+C 停止监控\n")

    try:
        while True:
            monitor_once()

            # 等待下次检查
            next_check = datetime.now().timestamp() + interval_hours * 3600
            next_check_time = datetime.fromtimestamp(next_check).strftime('%Y-%m-%d %H:%M:%S')
            print(f"\n⏳ 下次检查时间: {next_check_time}")

            time.sleep(interval_hours * 3600)

    except KeyboardInterrupt:
        print("\n\n👋 监控已停止")


# ─────────────────────────────────────────────
# 命令行入口
# ─────────────────────────────────────────────

def main() -> None:
    import sys

    if len(sys.argv) > 1 and sys.argv[1] == "--once":
        # 只执行一次检查（用于测试或 cron）
        monitor_once()
    else:
        # 持续监控模式
        monitor_loop(interval_hours=24)


if __name__ == "__main__":
    main()
