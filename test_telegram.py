"""
test_telegram.py - 测试 Telegram 推送
"""

from telegram_bot import send_message, load_tg_config
from datetime import datetime

def test_notification():
    """发送一条测试通知"""
    tg_config = load_tg_config()

    if not tg_config:
        print("❌ 未配置 Telegram")
        return

    token, chat_id = tg_config

    message = """🧪 <b>Telegram 推送测试</b>

这是一条测试消息，用于验证 Telegram Bot 是否正常工作。

如果你收到这条消息，说明配置成功！✅

⏰ """ + datetime.now().strftime('%Y-%m-%d %H:%M:%S')

    print("📤 正在发送测试消息...")
    if send_message(token, chat_id, message):
        print("✅ 测试消息发送成功！请检查你的 Telegram")
    else:
        print("❌ 测试消息发送失败")

if __name__ == "__main__":
    test_notification()
