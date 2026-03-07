"""
telegram_bot.py - Telegram 推送模块
支持：发送文字通知、图片、视频、批量媒体组（album）
依赖：requests（已在 requirements 中）
"""

import os
import json
import time
import requests
from pathlib import Path

# ─────────────────────────────────────────────
# 配置文件路径
# ─────────────────────────────────────────────

TG_CONFIG_PATH = "tg_config.json"

SUPPORTED_IMAGE_EXT = {".jpg", ".jpeg", ".png", ".webp"}
SUPPORTED_VIDEO_EXT = {".mp4", ".mov", ".avi", ".mkv"}
MAX_ALBUM_SIZE = 10          # Telegram 单次 sendMediaGroup 最多 10 个
MAX_FILE_MB    = 50          # Telegram Bot API 单文件上限 50 MB


# ─────────────────────────────────────────────
# 1. 配置管理
# ─────────────────────────────────────────────

def save_tg_config(bot_token: str, chat_id: str, path: str = TG_CONFIG_PATH) -> None:
    """将 Bot Token 和 Chat ID 保存到本地 JSON 文件。"""
    with open(path, "w", encoding="utf-8") as f:
        json.dump({"bot_token": bot_token, "chat_id": chat_id}, f, ensure_ascii=False, indent=2)
    print(f"✅ Telegram 配置已保存到 {path}")


def load_tg_config(path: str = TG_CONFIG_PATH) -> tuple[str, str] | None:
    """
    读取本地 Telegram 配置。
    返回 (bot_token, chat_id) 或 None（文件不存在时）。
    """
    if not os.path.exists(path):
        return None
    with open(path, "r", encoding="utf-8") as f:
        cfg = json.load(f)
    return cfg.get("bot_token", ""), cfg.get("chat_id", "")


def setup_tg_config() -> tuple[str, str]:
    """
    交互式引导用户输入 Bot Token 和 Chat ID，并保存。
    如果已有配置则询问是否复用。
    """
    existing = load_tg_config()
    if existing:
        token, chat_id = existing
        print(f"\n📋 检测到已保存的 Telegram 配置（Chat ID: {chat_id}）")
        reuse = input("是否使用此配置？(y/n，默认 y): ").strip().lower()
        if reuse != "n":
            return token, chat_id

    print("\n🤖 请配置 Telegram Bot：")
    print("  • Bot Token：在 @BotFather 创建 Bot 后获取")
    print("  • Chat ID ：向 @userinfobot 发消息即可获取您的 ID")
    print("             （频道请用 @频道名 或负数数字 ID）")
    token   = input("请输入 Bot Token: ").strip()
    chat_id = input("请输入 Chat ID : ").strip()
    save_tg_config(token, chat_id)
    return token, chat_id


# ─────────────────────────────────────────────
# 2. 核心发送函数
# ─────────────────────────────────────────────

def _api_url(token: str, method: str) -> str:
    return f"https://api.telegram.org/bot{token}/{method}"


def send_message(token: str, chat_id: str, text: str) -> bool:
    """发送纯文字消息，支持 HTML 格式。"""
    resp = requests.post(
        _api_url(token, "sendMessage"),
        data={"chat_id": chat_id, "text": text, "parse_mode": "HTML"},
        timeout=15,
    )
    return resp.ok


def _file_size_mb(path: str) -> float:
    return os.path.getsize(path) / (1024 * 1024)


def send_photo(token: str, chat_id: str, photo_path: str, caption: str = "") -> bool:
    """发送单张图片。"""
    if _file_size_mb(photo_path) > MAX_FILE_MB:
        print(f"  ⚠️  图片过大（>{MAX_FILE_MB}MB），跳过: {photo_path}")
        return False
    with open(photo_path, "rb") as f:
        resp = requests.post(
            _api_url(token, "sendPhoto"),
            data={"chat_id": chat_id, "caption": caption, "parse_mode": "HTML"},
            files={"photo": f},
            timeout=60,
        )
    return resp.ok


def send_video(token: str, chat_id: str, video_path: str, caption: str = "") -> bool:
    """发送单个视频。"""
    if _file_size_mb(video_path) > MAX_FILE_MB:
        print(f"  ⚠️  视频过大（>{MAX_FILE_MB}MB），跳过: {video_path}")
        return False
    with open(video_path, "rb") as f:
        resp = requests.post(
            _api_url(token, "sendVideo"),
            data={"chat_id": chat_id, "caption": caption, "parse_mode": "HTML"},
            files={"video": f},
            timeout=120,
        )
    return resp.ok


def send_media_group(
    token: str,
    chat_id: str,
    file_paths: list[str],
    caption: str = "",
) -> bool:
    """
    批量发送媒体组（最多 10 个）。
    caption 只附加在第一个媒体上。
    """
    if not file_paths:
        return True

    # 按 MAX_ALBUM_SIZE 分批
    success = True
    for batch_start in range(0, len(file_paths), MAX_ALBUM_SIZE):
        batch = file_paths[batch_start : batch_start + MAX_ALBUM_SIZE]
        media_json = []
        files_dict: dict = {}

        for idx, fp in enumerate(batch):
            ext = Path(fp).suffix.lower()
            field_name = f"file{idx}"

            if _file_size_mb(fp) > MAX_FILE_MB:
                print(f"  ⚠️  文件过大，跳过: {fp}")
                continue

            if ext in SUPPORTED_VIDEO_EXT:
                m_type = "video"
            else:
                m_type = "photo"

            entry: dict = {"type": m_type, "media": f"attach://{field_name}"}
            if idx == 0 and caption:
                entry["caption"]    = caption
                entry["parse_mode"] = "HTML"
            media_json.append(entry)
            files_dict[field_name] = open(fp, "rb")  # noqa: WPS515

        if not media_json:
            continue

        try:
            resp = requests.post(
                _api_url(token, "sendMediaGroup"),
                data={"chat_id": chat_id, "media": json.dumps(media_json)},
                files=files_dict,
                timeout=180,
            )
            if not resp.ok:
                print(f"  ❌ 媒体组发送失败: {resp.text}")
                success = False
        finally:
            for fobj in files_dict.values():
                fobj.close()

        time.sleep(1)  # 避免触发频率限制

    return success


# ─────────────────────────────────────────────
# 3. 高层接口：推送一个帖子文件夹
# ─────────────────────────────────────────────

def push_post_folder(
    token: str,
    chat_id: str,
    folder_path: str,
    shortcode: str = "",
) -> None:
    """
    扫描单个帖子的本地文件夹，将图片/视频推送到 Telegram。
    - 多文件 → sendMediaGroup（自动分批）
    - 单图片 → sendPhoto
    - 单视频 → sendVideo
    """
    folder = Path(folder_path)
    if not folder.exists():
        print(f"  ⚠️  文件夹不存在，跳过推送: {folder_path}")
        return

    media_files = sorted([
        str(p) for p in folder.iterdir()
        if p.suffix.lower() in SUPPORTED_IMAGE_EXT | SUPPORTED_VIDEO_EXT
    ])

    if not media_files:
        print(f"  ⚠️  未找到媒体文件，跳过: {folder_path}")
        return

    caption = f"📸 <b>{shortcode}</b>" if shortcode else ""

    print(f"  📤 推送 {len(media_files)} 个文件: {shortcode or folder_path}")

    if len(media_files) == 1:
        fp  = media_files[0]
        ext = Path(fp).suffix.lower()
        if ext in SUPPORTED_VIDEO_EXT:
            ok = send_video(token, chat_id, fp, caption)
        else:
            ok = send_photo(token, chat_id, fp, caption)
    else:
        ok = send_media_group(token, chat_id, media_files, caption)

    if ok:
        print(f"  ✅ 推送成功: {shortcode or folder_path}")
    else:
        print(f"  ❌ 推送失败: {shortcode or folder_path}")


def push_download_folder(
    token: str,
    chat_id: str,
    base_dir: str,
    target_user: str,
) -> None:
    """
    推送整个用户的下载目录（downloads/<target_user>/ 下每个子文件夹视为一个帖子）。
    先发送一条汇总通知，再逐帖推送。
    """
    user_dir = Path(base_dir) / target_user
    if not user_dir.exists():
        # 兼容 instaloader 平铺目录结构（无子文件夹）
        user_dir = Path(base_dir)

    # 找出所有子目录（每个子目录 = 一个帖子）
    sub_dirs = sorted([p for p in user_dir.iterdir() if p.is_dir()])

    if not sub_dirs:
        # 平铺结构：所有媒体直接在 user_dir 下
        push_post_folder(token, chat_id, str(user_dir), target_user)
        return

    total = len(sub_dirs)
    send_message(
        token, chat_id,
        f"🚀 开始推送 <b>@{target_user}</b> 的 {total} 个帖子..."
    )
    time.sleep(0.5)

    for i, sub in enumerate(sub_dirs, start=1):
        print(f"\n  [{i}/{total}] 推送文件夹: {sub.name}")
        push_post_folder(token, chat_id, str(sub), shortcode=sub.name)
        if i < total:
            time.sleep(1.5)  # 限速，避免触发 Telegram flood limit

    send_message(token, chat_id, f"✅ <b>@{target_user}</b> 全部推送完毕！共 {total} 个帖子。")
    print(f"\n🎉 所有帖子已推送到 Telegram！")
