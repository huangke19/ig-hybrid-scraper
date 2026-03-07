"""
scraper.py - IG 精准范围下载器（优化版）
依赖：utils.py（需在同目录下）

功能：
  1. 下载最新 N 条帖子
  2. 下载指定范围（第 M ~ 第 N 条）
  3. 下载单条帖子（URL 或 shortcode）
"""

import random
import time

import instaloader
from selenium.webdriver.common.by import By

from utils import (
    get_shortcode_from_url,
    human_sleep,
    init_driver,
    load_cookies_for_requests,
    load_cookies_for_selenium,
    retry,
)


# ─────────────────────────────────────────────
# 1. 链接提取模块
# ─────────────────────────────────────────────

def fetch_post_urls(target_user: str, required_count: int) -> list[str]:
    """
    用 Selenium 模拟滚动，从目标用户主页抓取帖子链接。
    - 使用 set 去重，O(1) 查找，大量帖子时性能显著优于 list。
    - 连续 MAX_NO_CHANGE 次页面高度不变才认为真正到底，
      避免懒加载未完成时提前停止。
    """
    MAX_NO_CHANGE = 3   # 连续高度不变的阈值
    SCROLL_PAUSE  = (2.0, 3.5)  # 每次滚动后随机等待区间（秒）

    driver = init_driver(headless=False)
    seen: set[str] = set()
    post_urls: list[str] = []

    try:
        # ── 注入 Cookie，恢复登录态 ──
        driver.get("https://www.instagram.com/")
        if load_cookies_for_selenium(driver):
            driver.refresh()
            time.sleep(2)

        print(f"\n🚀 正在检索 @{target_user} 的主页链接...")
        driver.get(f"https://www.instagram.com/{target_user}/")
        time.sleep(4)

        last_height = driver.execute_script("return document.body.scrollHeight")
        no_change_count = 0

        while len(post_urls) < required_count:
            # ── 收集当前页面所有帖子链接 ──
            for a in driver.find_elements(By.TAG_NAME, "a"):
                href = a.get_attribute("href") or ""
                if ("/p/" in href or "/reel/" in href) and href not in seen:
                    seen.add(href)
                    post_urls.append(href)

            if len(post_urls) >= required_count:
                break

            # ── 滚动到底部 ──
            driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
            time.sleep(random.uniform(*SCROLL_PAUSE))

            new_height = driver.execute_script("return document.body.scrollHeight")
            if new_height == last_height:
                no_change_count += 1
                if no_change_count >= MAX_NO_CHANGE:
                    print("  📄 已到达页面底部，停止滚动。")
                    break
            else:
                no_change_count = 0
            last_height = new_height

    finally:
        driver.quit()

    print(f"  🔗 共获取 {len(post_urls)} 条链接。")
    return post_urls


# ─────────────────────────────────────────────
# 2. 下载模块
# ─────────────────────────────────────────────

def _build_loader(save_folder: str) -> instaloader.Instaloader:
    """初始化 Instaloader 并完整注入 Cookie。"""
    L = instaloader.Instaloader(
        dirname_pattern=f"downloads/{save_folder}/{{target}}",
        download_videos=True,
        save_metadata=False,
        quiet=True,  # 减少 instaloader 自身的冗余输出
    )
    L.context._session.cookies = load_cookies_for_requests()
    return L


@retry(max_times=3, delay=10, backoff=1.5)
def _download_one(L: instaloader.Instaloader, shortcode: str, save_folder: str) -> None:
    """下载单个帖子，失败时由 @retry 自动重试。"""
    post = instaloader.Post.from_shortcode(L.context, shortcode)
    L.download_post(post, target=save_folder)


def download_selected_posts(urls: list[str], save_folder: str) -> None:
    """
    批量下载帖子。
    - 每次下载后调用 human_sleep 模拟真人行为。
    - 单条下载逻辑由 _download_one 封装，支持自动重试。
    """
    L = _build_loader(save_folder)
    total = len(urls)
    failed: list[str] = []

    for i, url in enumerate(urls, start=1):
        shortcode = get_shortcode_from_url(url)
        if not shortcode:
            print(f"  ⚠️  [{i}/{total}] 无法解析 shortcode，跳过: {url}")
            continue

        print(f"  📥 [{i}/{total}] 下载中: {shortcode}")
        try:
            _download_one(L, shortcode, save_folder)
            print(f"  ✅ [{i}/{total}] 完成: {shortcode}")
        except Exception as e:
            print(f"  ❌ [{i}/{total}] 最终失败，已记录: {shortcode} ({e})")
            failed.append(shortcode)

        if i < total:
            human_sleep()  # 最后一条不需要等待

    # ── 下载结束，汇报失败列表 ──
    if failed:
        print(f"\n⚠️  以下 {len(failed)} 条下载失败：")
        for sc in failed:
            print(f"    • {sc}")
    else:
        print("\n🎉 所有帖子下载成功！")


# ─────────────────────────────────────────────
# 3. 交互菜单
# ─────────────────────────────────────────────

def main() -> None:
    print("=" * 45)
    print("   IG 精准范围下载器（优化版）")
    print("=" * 45)

    target_user = input("\n请输入目标账号 ID（例如: jadeuly713）: ").strip()

    print("\n请选择下载范围：")
    print("  1. 下载最新的 N 条帖子")
    print("  2. 下载特定范围（第 M 到第 N 条）")
    print("  3. 下载单条帖子（输入 URL 或 shortcode）")
    choice = input("请输入数字 (1/2/3): ").strip()

    urls_to_download: list[str] = []

    if choice == "1":
        count = int(input("想下载前几条？ "))
        all_urls = fetch_post_urls(target_user, count)
        urls_to_download = all_urls[:count]

    elif choice == "2":
        start = int(input("从第几条开始？（从 1 开始计）"))
        end   = int(input("到第几条结束？ "))
        if start < 1 or end < start:
            print("❌ 范围输入有误，请确保 start >= 1 且 end >= start。")
            return
        all_urls = fetch_post_urls(target_user, end)
        urls_to_download = all_urls[start - 1 : end]

    elif choice == "3":
        raw = input("请输入帖子完整链接或 shortcode: ").strip()
        # 兼容两种输入：完整 URL 或纯 shortcode
        if raw.startswith("http"):
            urls_to_download = [raw]
        else:
            urls_to_download = [f"https://www.instagram.com/p/{raw}/"]

    else:
        print("❌ 无效选项，程序退出。")
        return

    if not urls_to_download:
        print("\n⚠️  未能获取到有效链接，请检查账号名或网络连接。")
        return

    print(f"\n✅ 准备就绪，即将下载 {len(urls_to_download)} 个帖子...\n")
    download_selected_posts(urls_to_download, target_user)
    print("\n✨ 任务全部完成！")


if __name__ == "__main__":
    main()
