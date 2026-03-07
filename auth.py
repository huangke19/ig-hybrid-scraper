"""
auth.py - 登录并保存 Cookie
运行此脚本，在弹出的浏览器中手动完成登录，回车后自动保存 cookies。
"""

import time
from utils import init_driver, save_cookies


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

        time.sleep(2)  # 等待页面数据写入完毕
        save_cookies(driver, path=cookie_path)

    finally:
        driver.quit()


if __name__ == "__main__":
    login_and_save()
