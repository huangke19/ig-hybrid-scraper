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

def download_user_photos(driver, target_user, max_posts=2):
    save_dir = f"downloads/{target_user}"
    os.makedirs(save_dir, exist_ok=True)
    
    print(f"正在前往 {target_user} 的主页搜集链接...")
    driver.get(f"https://www.instagram.com/{target_user}/")
    time.sleep(5)
    
    # 1. 搜集链接
    post_links = []
    a_tags = driver.find_elements(By.TAG_NAME, "a")
    for a in a_tags:
        href = a.get_attribute("href")
        if href and "/p/" in href and href not in post_links:
            post_links.append(href)
        if len(post_links) >= max_posts: break
    
    if not post_links:
        print("❌ 错误：在主页没找到任何帖子链接，请检查是否已登录或页面是否加载成功。")
        return

    print(f"收集到 {len(post_links)} 个帖子，开始深度抓取...")

    # 2. 进入详情页抓取
    for i, link in enumerate(post_links):
        print(f"正在处理第 {i+1} 个帖子: {link}")
        driver.get(link)
        time.sleep(5) 
        
        sub_count = 0
        downloaded_srcs = set()

        # 尝试翻页 12 次（处理轮播图）
        for step in range(12):
            # 💡 核心改进：只找帖子正中心的图片容器
            # 详情页的帖子大图通常在 article 标签内，或者特定的 class 组合中
            try:
                # 方案：寻找包含大图的 article 区域
                container = driver.find_element(By.TAG_NAME, "article")
                page_imgs = container.find_elements(By.TAG_NAME, "img")
            except:
                # 如果没找到 article，就降级回全页搜索
                page_imgs = driver.find_elements(By.TAG_NAME, "img")

            found_new_on_this_step = False
            for img in page_imgs:
                try:
                    src = img.get_attribute("src")
                    alt = img.get_attribute("alt") or ""
                    
                    # 过滤：必须是高清大图
                    # 1. 过滤掉头像和极其小的图 (宽高判断)
                    width = img.get_attribute("width")
                    if width and int(width) < 300: continue
                    
                    if src and src not in downloaded_srcs and ("fbcdn" in src or "instagram" in src):
                        # 排除头像关键词
                        if "profile" in alt.lower() or "头像" in alt: continue
                        
                        res = requests.get(src, timeout=10)
                        if res.status_code == 200 and len(res.content) > 40000: # 提升到40KB过滤小图
                            sub_count += 1
                            downloaded_srcs.add(src)
                            found_new_on_this_step = True
                            file_path = f"{save_dir}/post_{i+1}_img_{sub_count}.jpg"
                            with open(file_path, "wb") as f:
                                f.write(res.content)
                            print(f"   ✅ 第{step+1}页抓取: post_{i+1}_img_{sub_count}.jpg ({len(res.content)//1024}KB)")
                except: continue

            # --- 点击“下一步”并等待渲染 ---
            try:
                # 寻找按钮
                next_btn = driver.find_element(By.CSS_SELECTOR, "button[aria-label='Next'], button[aria-label='下一步']")
                if next_btn.is_displayed():
                    driver.execute_script("arguments[0].click();", next_btn)
                    # 💡 关键：点击后必须给 2 秒让大图从模糊变清晰
                    time.sleep(2) 
                else:
                    break
            except:
                # 找不到按钮说明是单图贴或到头了
                break 

    print(f"任务结束。")

# --- 主程序 ---

def main():
    username_to_scrape = "jadeuly713"  # <--- 在这里修改你想爬取的用户名
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
            download_user_photos(driver, username_to_scrape, max_posts=2)
        
    finally:
        print("程序执行完毕。")
        driver.quit()

if __name__ == "__main__":
    main()