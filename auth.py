"""
auth.py - 登录并保存 Cookie
运行此脚本，在弹出的浏览器中手动完成登录，回车后自动保存 cookies。
可选：顺带配置 Telegram Bot，以便 scraper.py 直接使用。
"""

import time
from utils import init_driver, save_cookies
from telegram_bot import load_tg_config, setup_tg_config, send_message


def login_and_save(cookie_path: str = "cookies.pkl") -> None:
    driver = init_driver(headless=False)  # 登录必须有界面
    try:
        driver.get("https://www.instagram.com/accounts/login/")

        print("=" * 50)
        print("请在弹出的浏览器中完成登录：")
        print("  1. 输入账号和密码")
        print("  2. 完成双重验证（如有）")
        print("  3. 确认已进入首页后，回到此处按回车")
        print("=" * 50)
        input("👉 登录完成后按回车继续...")

        time.sleep(0.5)  # 等待页面数据写入完毕
        save_cookies(driver, path=cookie_path)

    finally:
        driver.quit()


def setup_telegram_optional() -> None:
    """
    可选步骤：配置 Telegram Bot。
    如果已有配置则提示复用；用户可选择跳过。
    """
    print("\n" + "─" * 50)
    existing = load_tg_config()
    if existing:
        token, chat_id = existing
        print(f"📋 检测到已保存的 Telegram 配置（Chat ID: {chat_id}）")
        print("  1 - 重新配置")
        print("  2 - 保留现有配置")
        choice = input("请输入 (1/2，默认 2): ").strip()
        if choice != "1":
            print("  ✅ 保留现有 Telegram 配置。")
            return

    print("\n是否现在配置 Telegram Bot？（配置后 scraper.py 可直接推送内容）")
    print("  1 - 是，现在配置")
    print("  2 - 否，稍后配置")
    choice = input("请输入 (1/2，默认 2): ").strip()
    if choice != "1":
        print("  ℹ️  已跳过 Telegram 配置，可在运行 scraper.py 时再配置。")
        return

    token, chat_id = setup_tg_config()

    # 发送测试消息验证配置是否正确
    print("\n🔔 正在发送测试消息验证配置...")
    ok = send_message(token, chat_id, "✅ <b>IG 下载器</b> Telegram 推送配置成功！")
    if ok:
        print("  ✅ 测试消息发送成功，配置有效！")
    else:
        print("  ❌ 测试消息发送失败，请检查 Bot Token 和 Chat ID 是否正确。")
        print("     提示：确保已向 Bot 发送过至少一条消息（私聊），或 Bot 已加入目标频道/群组。")


if __name__ == "__main__":
    print("=" * 50)
    print("   IG 下载器 - 登录 & 配置向导")
    print("=" * 50)

    # Step 1: Instagram 登录
    login_and_save()

    # Step 2: 可选配置 Telegram
    setup_telegram_optional()

    print("\n✨ 初始化完成！现在可以运行 scraper.py 开始下载。")
