import os
import pickle
import re
import instaloader
from pathlib import Path

# --- 工具函数 ---

def extract_shortcode(url_or_code: str) -> str:
    """从URL或纯字符中提取Shortcode"""
    match = re.search(r'/(p|reel|tv)/([A-Za-z0-9_-]+)', url_or_code)
    if match:
        return match.group(2)
    if re.match(r'^[A-Za-z0-9_-]+$', url_or_code):
        return url_or_code
    raise ValueError("无效的链接或 Shortcode")

def load_cookies_to_instaloader(L: instaloader.Instaloader, cookie_path="cookies.pkl"):
    """将 Selenium 保存的 pickle cookies 注入到 Instaloader"""
    if not os.path.exists(cookie_path):
        print(f"❌ 错误：找不到 {cookie_path}，请先运行 auth.py 完成登录！")
        return False
    
    try:
        with open(cookie_path, "rb") as f:
            cookies = pickle.load(f)
            
        # 转换为 Requests 兼容的格式
        session = L.context._session
        for cookie in cookies:
            session.cookies.set(cookie['name'], cookie['value'], domain='.instagram.com')
        
        # 验证登录状态（可选）
        # L.test_login() 
        print("✅ 已成功从 cookies.pkl 加载登录 Session")
        return True
    except Exception as e:
        print(f"❌ 加载 Cookies 失败: {e}")
        return False

# --- 主逻辑 ---

def main():
    print("=== IG 整合版下载器 (Selenium 登录 + Instaloader 下载) ===")
    
    # 1. 初始化 Instaloader
    L = instaloader.Instaloader(
        dirname_pattern="downloads/{target}",
        filename_pattern="{date_utc}_UTC_{shortcode}",
        download_pictures=True,
        download_videos=True, # 默认开启视频
        download_video_thumbnails=False,
        save_metadata=False,
        post_metadata_txt_pattern=""
    )

    # 2. 加载登录状态
    if not load_cookies_to_instaloader(L):
        return

    # 3. 交互菜单
    print("\n1. 下载单个帖子 (Post/Reel)")
    print("2. 下载用户主页 (Profile)")
    choice = input("请选择 (1/2): ").strip()

    try:
        if choice == '1':
            target = input("请输入帖子链接或 Shortcode: ").strip()
            shortcode = extract_shortcode(target)
            print(f"🚀 正在抓取帖子: {shortcode}...")
            post = instaloader.Post.from_shortcode(L.context, shortcode)
            L.download_post(post, target="single_posts")
            
        elif choice == '2':
            username = input("请输入目标用户名: ").strip()
            max_num = input("下载前多少篇？(直接回车全部下载): ").strip()
            max_num = int(max_num) if max_num.isdigit() else None
            
            print(f"🚀 正在检索 @{username} 的帖子...")
            profile = instaloader.Profile.from_username(L.context, username)
            
            count = 0
            for post in profile.get_posts():
                if max_num and count >= max_num:
                    break
                
                print(f"正在下载第 {count+1} 篇: {post.shortcode}")
                L.download_post(post, target=profile.username)
                count += 1
                
        print("\n✅ 任务完成！文件保存在 downloads 文件夹下。")

    except Exception as e:
        print(f"❌ 运行中出错: {e}")

if __name__ == "__main__":
    main()