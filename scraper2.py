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

# --- 1. 提取 Shortcode 的工具函数 ---
def get_shortcode_from_url(url):
    match = re.search(r'/(p|reel|tv)/([A-Za-z0-9_-]+)', url)
    return match.group(2) if match else None

# --- 2. 使用 Selenium 获取所有帖子链接 ---
def fetch_post_urls(target_user, limit=5):
    options = webdriver.ChromeOptions()
    options.add_argument("--disable-blink-features=AutomationControlled")
    driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=options)
    
    post_urls = []
    try:
        driver.get("https://www.instagram.com/")
        # 加载已有的 Cookies
        if os.path.exists("cookies.pkl"):
            with open("cookies.pkl", "rb") as f:
                for cookie in pickle.load(f):
                    driver.add_cookie(cookie)
            driver.refresh()
            time.sleep(3)

        print(f"🚀 正在模拟浏览器访问 @{target_user}...")
        driver.get(f"https://www.instagram.com/{target_user}/")
        time.sleep(5)

        # 模拟滚动以加载更多链接
        last_height = driver.execute_script("return document.body.scrollHeight")
        while len(post_urls) < limit:
            a_tags = driver.find_elements(By.TAG_NAME, "a")
            for a in a_tags:
                href = a.get_attribute("href")
                if href and "/p/" in href and href not in post_urls:
                    post_urls.append(href)
            
            driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
            time.sleep(2)
            new_height = driver.execute_script("return document.body.scrollHeight")
            if new_height == last_height: break
            last_height = new_height
            
    finally:
        driver.quit()
    return post_urls[:limit]

# --- 3. 使用 Instaloader 下载指定 URL ---
def download_with_instaloader(urls):
    L = instaloader.Instaloader(
        dirname_pattern="downloads/{target}",
        download_videos=True,
        save_metadata=False
    )
    
    # 注入 Cookie 避免 Instaloader 再次触发 429
    if os.path.exists("cookies.pkl"):
        with open("cookies.pkl", "rb") as f:
            cookies = pickle.load(f)
            for cookie in cookies:
                L.context._session.cookies.set(cookie['name'], cookie['value'], domain='.instagram.com')
        print("✅ Instaloader 已同步 Session")

    for url in urls:
        shortcode = get_shortcode_from_url(url)
        if not shortcode: continue
        
        print(f"📥 正在下载帖子: {shortcode}")
        try:
            post = instaloader.Post.from_shortcode(L.context, shortcode)
            L.download_post(post, target="hybrid_download")
            # 必须设置随机延迟，否则下载多图贴时仍会报 429
            time.sleep(random.uniform(3, 7))
        except Exception as e:
            print(f"❌ 下载 {shortcode} 失败: {e}")

# --- 执行 ---
if __name__ == "__main__":
    target = "jadeuly713"
    # 第一步：模拟浏览器拿链接
    urls = fetch_post_urls(target, limit=3)
    print(f"🔗 成功获取 {len(urls)} 个链接")
    
    # 第二步：发给 Instaloader 下载
    if urls:
        download_with_instaloader(urls)