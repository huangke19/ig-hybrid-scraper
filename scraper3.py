import os
import pickle
import time
import random
import re
import instaloader
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from webdriver_manager.chrome import ChromeDriverManager

# --- 1. 工具函数 ---

def get_shortcode_from_url(url):
    """从详情页 URL 提取 Shortcode"""
    match = re.search(r'/(p|reel|tv)/([A-Za-z0-9_-]+)', url)
    return match.group(2) if match else None

def init_driver():
    """初始化带防检测参数的浏览器"""
    options = webdriver.ChromeOptions()
    options.add_argument("--disable-blink-features=AutomationControlled")
    options.add_experimental_option("excludeSwitches", ["enable-automation"])
    return webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=options)

# --- 2. 链接提取模块 ---

def fetch_post_urls(target_user, required_count):
    """使用 Selenium 模拟滚动，直到抓取到足够数量的链接"""
    driver = init_driver()
    post_urls = []
    
    try:
        driver.get("https://www.instagram.com/")
        if os.path.exists("cookies.pkl"):
            with open("cookies.pkl", "rb") as f:
                for cookie in pickle.load(f):
                    driver.add_cookie(cookie)
            driver.refresh()
            time.sleep(2)

        print(f"🚀 正在检索 @{target_user} 的主页链接...")
        driver.get(f"https://www.instagram.com/{target_user}/")
        time.sleep(4)

        # 循环滚动，直到抓取的链接数量达到我们需要范围的最大值
        last_height = driver.execute_script("return document.body.scrollHeight")
        while len(post_urls) < required_count:
            a_tags = driver.find_elements(By.TAG_NAME, "a")
            for a in a_tags:
                href = a.get_attribute("href")
                if href and "/p/" in href and href not in post_urls:
                    post_urls.append(href)
            
            if len(post_urls) >= required_count: break
            
            driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
            time.sleep(2)
            new_height = driver.execute_script("return document.body.scrollHeight")
            if new_height == last_height: break
            last_height = new_height
            
    finally:
        driver.quit()
    return post_urls

# --- 3. 下载模块 ---

def download_selected_posts(urls, save_folder):
    """使用 Instaloader 下载列表中的 URL"""
    L = instaloader.Instaloader(
        dirname_pattern=f"downloads/{save_folder}/{{target}}",
        download_videos=True,
        save_metadata=False
    )
    
    # 同步 Cookie
    if os.path.exists("cookies.pkl"):
        with open("cookies.pkl", "rb") as f:
            for cookie in pickle.load(f):
                L.context._session.cookies.set(cookie['name'], cookie['value'], domain='.instagram.com')

    for i, url in enumerate(urls):
        shortcode = get_shortcode_from_url(url)
        if not shortcode: continue
        
        print(f"📥 [{i+1}/{len(urls)}] 正在下载: {shortcode}")
        try:
            post = instaloader.Post.from_shortcode(L.context, shortcode)
            L.download_post(post, target=save_folder)
            time.sleep(random.uniform(4, 8)) # 严格延时防封
        except Exception as e:
            print(f"❌ 下载失败 {shortcode}: {e}")

# --- 4. 交互菜单 ---

def main():
    print("=== IG 精准范围下载器 (Hybrid) ===")
    target_user = input("请输入目标账号 ID (例如: jadeuly713): ").strip()
    
    print("\n请选择下载范围：")
    print("1. 下载最新的 N 条帖子 (例如: 前 5 条)")
    print("2. 下载特定范围 (例如: 第 3 到第 8 条)")
    print("3. 下载指定的单条帖子 (输入 URL 或 Shortcode)")
    choice = input("请输入数字 (1/2/3): ").strip()

    urls_to_download = []
    
    if choice == '1':
        count = int(input("想下载前几条？ "))
        all_urls = fetch_post_urls(target_user, count)
        urls_to_download = all_urls[:count]
        
    elif choice == '2':
        start = int(input("从第几条开始？ (从1开始计) "))
        end = int(input("到第几条结束？ "))
        all_urls = fetch_post_urls(target_user, end)
        urls_to_download = all_urls[start-1:end] # 列表切片
        
    elif choice == '3':
        single_url = input("请输入帖子的完整链接: ").strip()
        urls_to_download = [single_url]
    
    if urls_to_download:
        print(f"\n✅ 准备绪，即将下载 {len(urls_to_download)} 个帖子...")
        download_selected_posts(urls_to_download, target_user)
        print("\n✨ 任务全部完成！")
    else:
        print("未能获取到有效链接，请检查账号或网络。")

if __name__ == "__main__":
    main()