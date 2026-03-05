import os
import re
import time
import random
import itertools
from tqdm import tqdm
import instaloader

def extract_shortcode(url_or_code: str) -> str:
    """从完整URL或shortcode中提取shortcode"""
    match = re.search(r'/(p|reel|tv)/([A-Za-z0-9_-]+)', url_or_code)
    if match:
        return match.group(2)
    if re.match(r'^[A-Za-z0-9_-]+$', url_or_code):
        return url_or_code
    raise ValueError("无法解析链接，请输入正确的 URL 或 Shortcode")

def main():
    print("=== Instagram 交互式下载器 ===")
    
    # 1. 选择模式
    print("\n请选择下载模式：")
    print("1. 下载单个帖子 (Post/Reel)")
    print("2. 下载整个用户主页 (Profile)")
    choice = input("请输入数字 (1 或 2): ").strip()

    # 2. 根据模式获取目标
    target_input = ""
    if choice == '1':
        target_input = input("请输入帖子链接或 Shortcode: ").strip()
    else:
        target_input = input("请输入用户 ID (例如: natgeo): ").strip()

    # 3. 登录选项
    use_login = input("\n是否需要登录？(y/n) [下载私密账号或被限制时需要]: ").lower() == 'y'
    user, pw = None, None
    if use_login:
        user = input("请输入用户名: ").strip()
        pw = input("请输入密码: ").strip()

    # 4. 其他配置
    max_posts = 0
    if choice == '2':
        max_posts_str = input("最多下载多少篇？(直接回车代表全部): ").strip()
        max_posts = int(max_posts_str) if max_posts_str.isdigit() else 0
    
    download_videos = input("是否下载视频？(y/n, 默认 n): ").lower() == 'y'

    # ====================== 初始化 Instaloader ======================
    L = instaloader.Instaloader(
        dirname_pattern="downloads/{target}",
        filename_pattern="{date_utc}_UTC_{shortcode}_{typename}",
        download_pictures=True,
        download_videos=download_videos,
        download_video_thumbnails=False,
        save_metadata=False,
        quiet=False
    )

    # 登录逻辑
    if use_login and user and pw:
        try:
            print(f"正在登录 {user}...")
            L.login(user, pw)
            print("✅ 登录成功！")
        except Exception as e:
            print(f"❌ 登录失败: {e}")
            return

    # ====================== 执行下载 ======================
    try:
        if choice == '1':
            shortcode = extract_shortcode(target_input)
            print(f"🚀 正在处理帖子: {shortcode}")
            post = instaloader.Post.from_shortcode(L.context, shortcode)
            L.download_post(post, target="single_posts")
            print("✅ 下载完成！文件保存在 downloads/single_posts")
        
        elif choice == '2':
            print(f"🚀 正在处理用户 @{target_input}...")
            profile = instaloader.Profile.from_username(L.context, target_input)
            posts = profile.get_posts()
            
            if max_posts > 0:
                posts = itertools.islice(posts, max_posts)

            downloaded = 0
            for post in tqdm(posts, desc="下载进度", unit="帖"):
                L.download_post(post, target=profile.username)
                downloaded += 1
                # 随机延时防封
                time.sleep(random.uniform(1.5, 4.0))
            
            print(f"✅ 下载完成！共处理 {downloaded} 篇帖子。")
            
    except Exception as e:
        print(f"❌ 运行出错: {e}")

if __name__ == "__main__":
    main()