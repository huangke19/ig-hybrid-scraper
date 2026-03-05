import pickle
import os
import time
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager

def init_driver():
    options = webdriver.ChromeOptions()
    # 模拟真实浏览器，避免被识别为爬虫
    options.add_argument("--disable-blink-features=AutomationControlled")
    driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=options)
    return driver

def save_cookies(driver, path="cookies.pkl"):
    """将当前浏览器的 cookies 保存到本地文件"""
    with open(path, "wb") as file:
        pickle.dump(driver.get_cookies(), file)
    print(f"Cookies 已保存到 {path}")

def login_and_save():
    driver = init_driver()
    driver.get("https://www.instagram.com/accounts/login/")
    
    print("请在弹出的浏览器中完成登录（包括输入账号、密码和验证码）。")
    print("登录成功并看到首页后，请回到这里按回车键...")
    
    input("等待登录中...完成后按回车继续")
    
    # 稍微等两秒确保页面数据加载完
    time.sleep(2)
    save_cookies(driver)
    driver.quit()

if __name__ == "__main__":
    login_and_save()