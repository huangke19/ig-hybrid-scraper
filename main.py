import pickle
import time
import requests
import os
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from webdriver_manager.chrome import ChromeDriverManager

# --- 基础配置模块 ---

def init_driver():
    options = webdriver.ChromeOptions()
    options.add_experimental_option("excludeSwitches", ["enable-automation"])
    options.add_experimental_option('useAutomationExtension', False)
    options.add_argument("--window-size=1200,900")
    # 模拟真实浏览器 User-Agent
    options.add_argument("user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")
    driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=options)
    return driver

def load_cookies(driver, path="cookies.pkl"):
    if not os.path.exists(path):
        print(f"错误：找不到 {path}，请先运行 auth.py 登录！")
        return False
    with open(path, "rb") as file:
        cookies = pickle.load(file)
        for cookie in cookies:
            driver.add_cookie(cookie)
    return True

def handle_popups(driver):
    """处理‘开启通知’等弹窗"""
    try:
        wait = WebDriverWait(driver, 5)
        # 尝试点击“稍后再说”
        not_now_btn = wait.until(EC.element_to_be_clickable((By.XPATH, "//button[contains(text(), 'Not Now') or contains(text(), '稍后再说')]")))
        not_now_btn.click()
        print("已清理弹窗。")
    except:
        pass

# --- 核心爬取模块 ---

def download_user_photos(driver, target_user, max_count=5):
    save_dir = f"downloads/{target_user}"
    os.makedirs(save_dir, exist_ok=True)
    
    print(f"正在前往 {target_user} 的主页...")
    driver.get(f"https://www.instagram.com/{target_user}/")
    
    # 强制等待 8 秒，不管页面加载到哪了，直接开始抓
    print("等待页面渲染中（8秒）...")
    time.sleep(8) 

    downloaded_urls = set()
    count = 0
    
    # 获取页面源码存入调试文件（如果还是失败，我们可以分析这个文件）
    with open("debug_page.html", "w", encoding="utf-8") as f:
        f.write(driver.page_source)

    for scroll in range(3):
        # 尝试多种选择器，总有一个能抓到
        # 1. 直接抓所有 img 标签
        images = driver.find_elements(By.TAG_NAME, "img")
        print(f"滚动第 {scroll+1} 次: 发现 {len(images)} 个 img 标签")

        for img in images:
            try:
                src = img.get_attribute("src")
                alt = img.get_attribute("alt") or ""
                
                # 核心过滤逻辑升级：
                # - 必须有 src
                # - src 里通常包含 'fbcdn' 或 'instagram'
                # - alt 包含 "Photo" 或 "Image" 的通常是帖子，而 "profile" 是头像
                if src and src not in downloaded_urls:
                    if "150x150" in src or "profile" in alt.lower():
                        continue
                    
                    # 尝试下载
                    headers = {
                        "User-Agent": driver.execute_script("return navigator.userAgent;"),
                        "Referer": "https://www.instagram.com/"
                    }
                    
                    res = requests.get(src, headers=headers, timeout=15)
                    if res.status_code == 200:
                        count += 1
                        downloaded_urls.add(src)
                        file_path = f"{save_dir}/post_{count}.jpg"
                        with open(file_path, "wb") as f:
                            f.write(res.content)
                        print(f"✅ [成功] 下载到: {file_path}")
                    
                    if count >= max_count: break
            except Exception:
                continue

        if count >= max_count: break
        
        print("向下滚动一屏...")
        driver.execute_script("window.scrollBy(0, 1200);")
        time.sleep(3)

    print(f"任务结束，共抓取 {count} 张图片。")

# --- 主程序 ---

def main():
    username_to_scrape = "nasa"  # <--- 在这里修改你想爬取的用户名
    driver = init_driver()
    
    try:
        # 必须先访问域名才能注入 Cookie
        driver.get("https://www.instagram.com/")
        time.sleep(2)
        
        if load_cookies(driver):
            driver.refresh()
            time.sleep(3)
            handle_popups(driver)
            
            # 开始下载任务
            download_user_photos(driver, username_to_scrape, max_count=8)
        
    finally:
        print("程序执行完毕。")
        driver.quit()

if __name__ == "__main__":
    main()