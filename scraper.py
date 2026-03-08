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

import json
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
    save_urls_cache,
    load_urls_cache,
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
# 下载历史管理
# ─────────────────────────────────────────────

def load_downloaded_users() -> list[str]:
    """加载下载历史用户列表"""
    try:
        with open("downloaded_users.json", "r", encoding="utf-8") as f:
            return json.load(f)
    except FileNotFoundError:
        return []
    except json.JSONDecodeError:
        return []


def save_downloaded_user(username: str) -> None:
    """保存下载过的用户名到历史记录（去重）"""
    users = load_downloaded_users()
    if username not in users:
        users.append(username)
        with open("downloaded_users.json", "w", encoding="utf-8") as f:
            json.dump(users, f, ensure_ascii=False, indent=2)


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
        url = f"https://www.instagram.com/p/{post.shortcode}/"
        urls.append(url)
        if len(urls) >= required_count:
            break

    return urls[:required_count]  # 确保只返回请求的数量


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
                    # 达到所需数量立即停止
                    if len(post_urls) >= required_count:
                        break

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

    # 确保只返回请求的数量
    result = post_urls[:required_count]
    print(f"  🔗 共获取 {len(result)} 条链接。")
    return result


def fetch_post_urls(target_user: str, required_count: int, use_cache: bool = True) -> list[str]:
    """
    智能获取帖子链接：
    1. 如果启用缓存且缓存存在，使用缓存
    2. 否则，优先使用 API 方式，失败时自动回退到浏览器方式
    3. 获取后保存到缓存
    """
    # 尝试从缓存加载
    if use_cache:
        cached_urls = load_urls_cache(target_user)
        if cached_urls and len(cached_urls) >= required_count:
            print(f"  ✅ 使用缓存的链接")
            return cached_urls[:required_count]
        elif cached_urls:
            print(f"  ⚠️  缓存链接不足（需要 {required_count} 条，缓存有 {len(cached_urls)} 条），重新获取")

    # 缓存不存在或不足，重新获取
    try:
        print(f"\n🚀 正在获取 @{target_user} 的帖子链接（API 方式）...")
        urls = fetch_post_urls_via_api(target_user, required_count)
        print(f"  ✅ API 方式成功，共获取 {len(urls)} 条链接")

        # 保存到缓存
        if use_cache:
            save_urls_cache(target_user, urls)

        return urls
    except Exception as e:
        print(f"  ⚠️  API 方式失败: {e}")
        print(f"  🔄 切换到浏览器方式...")
        urls = fetch_post_urls_via_selenium(target_user, required_count)

        # 保存到缓存
        if use_cache:
            save_urls_cache(target_user, urls)

        return urls


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
        str(p) for p in base.rglob(f"*{shortcode}*")
        if p.is_file() and p.suffix.lower() in MEDIA_EXTS
    ])


def _build_files_index(base_dir: str) -> dict[str, list[str]]:
    """
    一次性扫描目录，建立 shortcode -> 文件列表 的索引。
    用于批量下载时避免重复扫描磁盘。
    返回: {shortcode: [file_path1, file_path2, ...]}
    """
    base = Path(base_dir)
    if not base.exists():
        return {}

    index: dict[str, list[str]] = {}
    for p in base.rglob("*"):
        if p.is_file() and p.suffix.lower() in MEDIA_EXTS:
            # 从文件名中提取 shortcode（假设格式为 {shortcode}_xxx）
            filename = p.name
            # shortcode 通常是文件名的第一部分（下划线之前）
            parts = filename.split("_")
            if parts:
                shortcode = parts[0]
                if shortcode not in index:
                    index[shortcode] = []
                index[shortcode].append(str(p))

    return index


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
    progress_callback=None,
) -> None:
    """
    批量下载帖子。

    参数：
      tg_config  : (bot_token, chat_id) 或 None（不推送）
      push_mode  : "each"  → 每条下载后立即推送
                   "batch" → 全部下载完毕后统一推送
                   "none"  → 不推送
      progress_callback: 可选回调，签名为 (progress, total, message)
    """
    total = len(urls)
    if progress_callback:
        progress_callback(0, total, "初始化下载器...")

    L = _build_loader(save_folder)
    failed: list[str] = []
    downloaded_items: list[tuple[list[str], str]] = []  # (files, shortcode)

    token, chat_id = tg_config if tg_config else ("", "")
    base_dir = config.download_base_dir if config else "downloads"
    base_dir = str(Path(base_dir) / save_folder)

    # 预扫描：一次性建立已下载文件索引
    print(f"  🔍 正在扫描已下载文件...")
    if progress_callback:
        progress_callback(0, total, "正在扫描已下载文件...")
    existing_files_index = _build_files_index(base_dir)
    if existing_files_index:
        print(f"  📂 找到 {len(existing_files_index)} 个已下载的帖子")

    for i, url in enumerate(urls, start=1):
        shortcode = get_shortcode_from_url(url)
        if not shortcode:
            print(f"  ⚠️  [{i}/{total}] 无法解析 shortcode，跳过: {url}")
            if progress_callback:
                progress_callback(i, total, f"跳过无效链接 ({i}/{total})")
            continue

        # 从索引中查找已存在的文件（无需重复扫描磁盘）
        existing_files = existing_files_index.get(shortcode, [])
        if existing_files:
            print(f"  ⏭️  [{i}/{total}] 已存在，跳过下载: {shortcode}（{len(existing_files)} 个文件）")

            # 已存在文件也支持推送
            if push_mode == "each" and tg_config:
                print(f"  📤 推送已存在内容: {shortcode}")
                if progress_callback:
                    progress_callback(i - 1, total, f"正在推送已存在内容: {shortcode} ({i}/{total})")
                _push_files(token, chat_id, existing_files, shortcode)

            if push_mode == "batch" and tg_config:
                downloaded_items.append((existing_files, shortcode))

            if progress_callback:
                progress_callback(i, total, f"已存在，处理完成: {shortcode} ({i}/{total})")
            continue

        print(f"  📥 [{i}/{total}] 下载中: {shortcode}")
        if progress_callback:
            progress_callback(i - 1, total, f"正在下载: {shortcode} ({i}/{total})")
        try:
            _download_one(L, shortcode, save_folder)
            print(f"  ✅ [{i}/{total}] 完成: {shortcode}")

            # 下载后动态扫描实际生成的文件
            if progress_callback:
                progress_callback(i - 1, total, f"正在整理文件: {shortcode} ({i}/{total})")
            files = _find_post_files(base_dir, shortcode)
            if files:
                print(f"        找到 {len(files)} 个媒体文件")
                # 更新索引
                existing_files_index[shortcode] = files
            else:
                print(f"  ⚠️  [{i}/{total}] 未在 {base_dir} 找到媒体文件，请检查下载目录")
            downloaded_items.append((files, shortcode))

            # ── 逐条推送模式 ──
            if push_mode == "each" and tg_config and files:
                print(f"  📤 实时推送: {shortcode}")
                if progress_callback:
                    progress_callback(i - 1, total, f"正在推送 Telegram: {shortcode} ({i}/{total})")
                _push_files(token, chat_id, files, shortcode)

            if progress_callback:
                progress_callback(i, total, f"已完成: {shortcode} ({i}/{total})")

        except Exception as e:
            print(f"  ❌ [{i}/{total}] 最终失败，已记录: {shortcode} ({e})")
            failed.append(shortcode)
            if progress_callback:
                progress_callback(i, total, f"失败: {shortcode} ({i}/{total})")

        if i < total:
            if progress_callback:
                progress_callback(i, total, f"等待下一条任务... ({i}/{total})")
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
        if progress_callback:
            progress_callback(total, total, f"开始批量推送 Telegram ({len(valid_items)} 条)...")
        send_message(token, chat_id, f"🚀 开始推送 <b>@{save_folder}</b> 的 {len(valid_items)} 个帖子...")
        for idx, (files, sc) in enumerate(valid_items, start=1):
            print(f"  [{idx}/{len(valid_items)}] 推送: {sc}")
            if progress_callback:
                progress_callback(total, total, f"Telegram 推送中: {sc} ({idx}/{len(valid_items)})")
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
    print("  1 - 是，推送到 Telegram")
    print("  2 - 否，仅本地保存")
    choice = input("请输入 (1/2，默认 2): ").strip()

    if choice != "1":
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


def batch_download_mode(users: list[str]) -> None:
    """批量下载多个用户的内容"""
    print(f"\n📦 批量下载模式：将下载 {len(users)} 个用户的内容")

    # 询问每个用户的下载数量
    try:
        count = int(input("每个用户下载多少条帖子？ "))
    except ValueError:
        print("❌ 无效输入")
        return

    # 询问 Telegram 推送设置
    tg_config, push_mode = ask_telegram_push()

    for i, user in enumerate(users, start=1):
        print(f"\n{'=' * 45}")
        print(f"  [{i}/{len(users)}] 正在处理: @{user}")
        print(f"{'=' * 45}")

        try:
            urls = fetch_post_urls(user, count)
            download_selected_posts(
                urls,
                user,
                tg_config=tg_config,
                push_mode=push_mode,
            )
            # 保存用户到下载历史
            save_downloaded_user(user)
        except Exception as e:
            print(f"  ❌ 用户 @{user} 下载失败: {e}")
            continue

    print("\n✨ 批量下载全部完成！")


# ─────────────────────────────────────────────
# 4. 交互菜单
# ─────────────────────────────────────────────

def main() -> None:
    print("=" * 45)
    print("   IG 精准范围下载器（优化版）")
    print("=" * 45)

    # 加载常用用户和下载历史
    favorite_users = config.favorite_users if config else []
    downloaded_users = load_downloaded_users()

    # 合并用户列表：常用用户优先，然后是下载历史中不在常用列表的用户
    all_users = []
    user_labels = []  # 用于显示标签（⭐ 或 📥）

    for user in favorite_users:
        all_users.append(user)
        user_labels.append("⭐")

    for user in downloaded_users:
        if user not in favorite_users:
            all_users.append(user)
            user_labels.append("📥")

    if all_users:
        print("\n用户列表（⭐常用 📥历史）：")
        for i, (user, label) in enumerate(zip(all_users, user_labels), start=1):
            print(f"  {i}. {label} {user}")
        print(f"  {len(all_users) + 1}. 输入其他用户名")
        print(f"  {len(all_users) + 2}. 批量下载（所有用户）")

        choice = input(f"\n请选择 (1-{len(all_users) + 2}): ").strip()

        try:
            choice_num = int(choice)
            if 1 <= choice_num <= len(all_users):
                target_user = all_users[choice_num - 1]
            elif choice_num == len(all_users) + 1:
                target_user = input("\n请输入目标账号 ID: ").strip()
            elif choice_num == len(all_users) + 2:
                # 批量下载模式
                batch_download_mode(all_users)
                return
            else:
                print("❌ 无效选项")
                return
        except ValueError:
            print("❌ 无效输入")
            return
    else:
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

    # 保存用户到下载历史
    save_downloaded_user(target_user)

    print("\n✨ 任务全部完成！")


if __name__ == "__main__":
    main()
