"""
scraper.py - IG 精准范围下载器（优化版）
依赖：utils.py、telegram_bot.py、config.py（需在同目录下）

功能：
  1. 下载最新 N 条帖子
  2. 下载指定范围（第 M ~ 第 N 条）
  3. 下载单条帖子（URL 或 shortcode）
  4. 下载完成后可选推送到 Telegram
  5. 支持从 config.yaml 读取配置
"""

import random
import time
from pathlib import Path

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
from telegram_bot import (
    send_message,
    send_media_group,
    send_photo,
    send_video,
    setup_tg_config,
    load_tg_config,
)

try:
    from config import Config
    config = Config()
except ImportError:
    config = None

MEDIA_EXTS = {".jpg", ".jpeg", ".png", ".webp", ".mp4", ".mov"}


# ─────────────────────────────────────────────
# 1. 链接提取模块
# ─────────────────────────────────────────────

def fetch_post_urls_via_api(target_user: str, required_count: int) -> list[str]:
    """
    使用 Instaloader API 快速获取帖子链接（无需浏览器）。
    速度快，但可能更容易被检测。
    """
    L = instaloader.Instaloader(
        quiet=True,
        max_connection_attempts=1  # 遇到错误立即失败，不等待重试
    )
    L.context._session.cookies = load_cookies_for_requests()

    profile = instaloader.Profile.from_username(L.context, target_user)
    posts = profile.get_posts()

    urls = []
    for post in posts:
        if len(urls) >= required_count:
            break
        url = f"https://www.instagram.com/p/{post.shortcode}/"
        urls.append(url)

    return urls


def fetch_post_urls_via_selenium(target_user: str, required_count: int) -> list[str]:
    """
    用 Selenium 模拟滚动，从目标用户主页抓取帖子链接。
    - 使用 set 去重，O(1) 查找，大量帖子时性能显著优于 list。
    - 连续 MAX_NO_CHANGE 次页面高度不变才认为真正到底，
      避免懒加载未完成时提前停止。
    - 滚动暂停时间从配置文件读取。
    """
    MAX_NO_CHANGE = 3
    if config:
        behavior = config.behavior_config
        SCROLL_PAUSE = (behavior.get('scroll_pause_min', 2.0), behavior.get('scroll_pause_max', 3.5))
    else:
        SCROLL_PAUSE = (2.0, 3.5)

    driver = init_driver(headless=False)
    seen: set[str] = set()
    post_urls: list[str] = []

    try:
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
            for a in driver.find_elements(By.TAG_NAME, "a"):
                href = a.get_attribute("href") or ""
                if ("/p/" in href or "/reel/" in href) and href not in seen:
                    seen.add(href)
                    post_urls.append(href)

            if len(post_urls) >= required_count:
                break

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


def fetch_post_urls(target_user: str, required_count: int) -> list[str]:
    """
    智能获取帖子链接：优先使用 API 方式，失败时自动回退到浏览器方式。
    - API 方式：快速，无需启动浏览器（推荐）
    - 浏览器方式：稳定，但速度较慢（备用）
    """
    try:
        print(f"\n🚀 正在获取 @{target_user} 的帖子链接（API 方式）...")
        urls = fetch_post_urls_via_api(target_user, required_count)
        print(f"  ✅ API 方式成功，共获取 {len(urls)} 条链接")
        return urls
    except Exception as e:
        print(f"  ⚠️  API 方式失败: {e}")
        print(f"  🔄 切换到浏览器方式...")
        return fetch_post_urls_via_selenium(target_user, required_count)


# ─────────────────────────────────────────────
# 2. 下载模块
# ─────────────────────────────────────────────

def _build_loader(save_folder: str) -> instaloader.Instaloader:
    """
    初始化 Instaloader 并完整注入 Cookie。
    使用平铺目录：所有文件存入 downloads/<save_folder>/
    文件名含 shortcode，便于下载后精确定位。
    配置项从 config.yaml 读取。
    """
    base_dir = config.download_base_dir if config else "downloads"
    download_videos = config.download_videos if config else True
    save_metadata = config.download_metadata if config else False

    L = instaloader.Instaloader(
        dirname_pattern=f"{base_dir}/{save_folder}",
        filename_pattern="{shortcode}_{filename}",
        download_videos=download_videos,
        save_metadata=save_metadata,
        quiet=True,
    )
    L.context._session.cookies = load_cookies_for_requests()
    return L


def _find_post_files(base_dir: str, shortcode: str) -> list[str]:
    """
    下载完成后，递归扫描 base_dir 中所有文件名包含 shortcode 的媒体文件。
    使用 rglob 兼容 instaloader 生成子目录或平铺两种结构。
    """
    base = Path(base_dir)
    if not base.exists():
        return []
    return sorted([
        str(p) for p in base.rglob("*")
        if p.is_file()
        and p.suffix.lower() in MEDIA_EXTS
        and shortcode in p.name
    ])


@retry(max_times=None, delay=None, backoff=1.5)
def _download_one(L: instaloader.Instaloader, shortcode: str, save_folder: str) -> None:
    """
    下载单个帖子，失败时由 @retry 自动重试。
    重试次数和延时从配置文件读取。
    """
    post = instaloader.Post.from_shortcode(L.context, shortcode)
    L.download_post(post, target=save_folder)


def _push_files(token: str, chat_id: str, files: list[str], shortcode: str) -> None:
    """将一组媒体文件推送到 Telegram，自动选择最合适的发送方式。"""
    caption = f"📸 <b>{shortcode}</b>"
    if len(files) == 1:
        fp = files[0]
        ext = Path(fp).suffix.lower()
        ok = send_video(token, chat_id, fp, caption) if ext in {".mp4", ".mov"} else send_photo(token, chat_id, fp, caption)
    else:
        ok = send_media_group(token, chat_id, files, caption)

    if ok:
        print(f"  ✅ 推送成功: {shortcode}（{len(files)} 个文件）")
    else:
        print(f"  ❌ 推送失败: {shortcode}")


def download_selected_posts(
    urls: list[str],
    save_folder: str,
    tg_config: tuple[str, str] | None = None,
    push_mode: str = "none",
) -> None:
    """
    批量下载帖子。

    参数：
      tg_config  : (bot_token, chat_id) 或 None（不推送）
      push_mode  : "each"  → 每条下载后立即推送
                   "batch" → 全部下载完毕后统一推送
                   "none"  → 不推送
    """
    L = _build_loader(save_folder)
    total = len(urls)
    failed: list[str] = []
    downloaded_items: list[tuple[list[str], str]] = []  # (files, shortcode)

    token, chat_id = tg_config if tg_config else ("", "")
    base_dir = config.download_base_dir if config else "downloads"
    base_dir = str(Path(base_dir) / save_folder)

    for i, url in enumerate(urls, start=1):
        shortcode = get_shortcode_from_url(url)
        if not shortcode:
            print(f"  ⚠️  [{i}/{total}] 无法解析 shortcode，跳过: {url}")
            continue

        print(f"  📥 [{i}/{total}] 下载中: {shortcode}")
        try:
            _download_one(L, shortcode, save_folder)
            print(f"  ✅ [{i}/{total}] 完成: {shortcode}")

            # 下载后动态扫描实际生成的文件
            files = _find_post_files(base_dir, shortcode)
            if files:
                print(f"        找到 {len(files)} 个媒体文件")
            else:
                print(f"  ⚠️  [{i}/{total}] 未在 {base_dir} 找到媒体文件，请检查下载目录")
            downloaded_items.append((files, shortcode))

            # ── 逐条推送模式 ──
            if push_mode == "each" and tg_config and files:
                print(f"  📤 实时推送: {shortcode}")
                _push_files(token, chat_id, files, shortcode)

        except Exception as e:
            print(f"  ❌ [{i}/{total}] 最终失败，已记录: {shortcode} ({e})")
            failed.append(shortcode)

        if i < total:
            human_sleep()

    # ── 下载结束，汇报失败列表 ──
    if failed:
        print(f"\n⚠️  以下 {len(failed)} 条下载失败：")
        for sc in failed:
            print(f"    • {sc}")
    else:
        print("\n🎉 所有帖子下载成功！")

    # ── 批量推送模式 ──
    if push_mode == "batch" and tg_config:
        valid_items = [(f, sc) for f, sc in downloaded_items if f]
        print(f"\n📤 开始批量推送 {len(valid_items)} 个帖子到 Telegram...")
        send_message(token, chat_id, f"🚀 开始推送 <b>@{save_folder}</b> 的 {len(valid_items)} 个帖子...")
        for idx, (files, sc) in enumerate(valid_items, start=1):
            print(f"  [{idx}/{len(valid_items)}] 推送: {sc}")
            _push_files(token, chat_id, files, sc)
            if idx < len(valid_items):
                time.sleep(1.5)
        send_message(token, chat_id, f"✅ <b>@{save_folder}</b> 全部推送完毕！共 {len(valid_items)} 个帖子。")
        print("🎉 所有帖子已推送到 Telegram！")


# ─────────────────────────────────────────────
# 3. Telegram 推送配置询问
# ─────────────────────────────────────────────

def ask_telegram_push() -> tuple[tuple[str, str] | None, str]:
    """
    询问用户是否推送到 Telegram，以及推送方式。
    如果配置文件中已启用 Telegram，则直接使用配置。
    返回 (tg_config, push_mode)。
    """
    # 优先从配置文件读取
    if config and config.telegram_enabled:
        token = config.telegram_token
        chat_id = config.telegram_chat_id
        push_mode = config.telegram_push_mode
        if token and chat_id:
            print(f"\n✅ 已从配置文件加载 Telegram 设置（推送模式: {push_mode}）")
            return (token, chat_id), push_mode

    print("\n" + "─" * 45)
    print("📬 是否将下载内容推送到 Telegram？")
    print("  y - 是，推送到 Telegram")
    print("  n - 否，仅本地保存")
    choice = input("请输入 (y/n，默认 n): ").strip().lower()

    if choice != "y":
        print("  ℹ️  已跳过 Telegram 推送。")
        return None, "none"

    tg_config = setup_tg_config()

    print("\n请选择推送时机：")
    print("  1 - 每条下载完立即推送（实时）")
    print("  2 - 全部下载完成后统一推送")
    mode_choice = input("请输入 (1/2，默认 2): ").strip()

    push_mode = "each" if mode_choice == "1" else "batch"
    mode_label = "实时逐条推送" if push_mode == "each" else "下载完成后批量推送"
    print(f"  ✅ 已选择：{mode_label}")

    return tg_config, push_mode


# ─────────────────────────────────────────────
# 4. 交互菜单
# ─────────────────────────────────────────────

def main() -> None:
    print("=" * 45)
    print("   IG 精准范围下载器（优化版）")
    print("=" * 45)

    target_user = input("\n请输入目标账号 ID（例如: jadeuly713）: ").strip()

    print("\n请选择下载范围：")
    print("  1. 下载最新的 N 条帖子")
    print("  2. 下载特定范围（第 M 到第 N 条）")
    print("  3. 下载指定第几条帖子")
    print("  4. 下载单条帖子（输入 URL 或 shortcode）")
    choice = input("请输入数字 (1/2/3/4): ").strip()

    # 先询问 Telegram 推送设置，避免浏览器打开后还要等待输入
    tg_config, push_mode = ask_telegram_push()

    urls_to_download: list[str] = []

    if choice == "1":
        count = int(input("\n想下载前几条？ "))
        all_urls = fetch_post_urls(target_user, count)
        urls_to_download = all_urls[:count]

    elif choice == "2":
        start = int(input("\n从第几条开始？（从 1 开始计）"))
        end   = int(input("到第几条结束？ "))
        if start < 1 or end < start:
            print("❌ 范围输入有误，请确保 start >= 1 且 end >= start。")
            return
        all_urls = fetch_post_urls(target_user, end)
        urls_to_download = all_urls[start - 1 : end]

    elif choice == "3":
        position = int(input("\n请输入要下载第几条帖子？（从 1 开始计）"))
        if position < 1:
            print("❌ 位置必须大于等于 1。")
            return
        all_urls = fetch_post_urls(target_user, position)
        if position <= len(all_urls):
            urls_to_download = [all_urls[position - 1]]
        else:
            print(f"❌ 该账号只有 {len(all_urls)} 条帖子，无法获取第 {position} 条。")
            return

    elif choice == "4":
        raw = input("\n请输入帖子完整链接或 shortcode: ").strip()
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
    download_selected_posts(
        urls_to_download,
        target_user,
        tg_config=tg_config,
        push_mode=push_mode,
    )
    print("\n✨ 任务全部完成！")


if __name__ == "__main__":
    main()
