"""
web_app.py - IG 爬虫 Web UI
基于 Flask 的 Web 界面，提供下载管理、监控配置、历史记录等功能
"""

from flask import Flask, render_template, request, jsonify, send_from_directory
from flask_socketio import SocketIO, emit
from pathlib import Path
import json
import threading
import logging
from datetime import datetime

from scraper import (
    fetch_post_urls,
    download_selected_posts,
    load_downloaded_users,
    save_downloaded_user,
)
from monitor import check_new_posts, load_monitor_history
from telegram_bot import load_tg_config, save_tg_config, send_message
from utils import get_shortcode_from_url

try:
    from config import Config
    config = Config()
except ImportError:
    config = None

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger(__name__)

app = Flask(__name__)
app.config['SECRET_KEY'] = 'ig-scraper-secret-key'
socketio = SocketIO(app, cors_allowed_origins="*")

logger.info("Flask 应用启动")

# 全局任务状态
download_tasks = {}
task_id_counter = 0


# ─────────────────────────────────────────────
# 首页
# ─────────────────────────────────────────────

@app.route('/')
def index():
    return render_template('index.html')


# ─────────────────────────────────────────────
# 用户管理 API
# ─────────────────────────────────────────────

@app.route('/api/users', methods=['GET'])
def get_users():
    """获取用户列表（常用 + 历史）"""
    logger.info("请求用户列表")
    favorite_users = config.favorite_users if config else []
    downloaded_users = load_downloaded_users()

    users = []
    for user in favorite_users:
        users.append({'username': user, 'type': 'favorite'})

    for user in downloaded_users:
        if user not in favorite_users:
            users.append({'username': user, 'type': 'history'})

    logger.info(f"返回 {len(users)} 个用户")
    return jsonify({'users': users})


# ─────────────────────────────────────────────
# 下载任务 API
# ─────────────────────────────────────────────

@app.route('/api/download', methods=['POST'])
def start_download():
    """启动下载任务"""
    global task_id_counter

    data = request.json
    username = data.get('username', '').strip()
    download_type = data.get('type', 'latest')
    count = data.get('count', 10)
    start_pos = data.get('start', 1)
    end_pos = data.get('end', 10)
    position = data.get('position', 1)
    url = data.get('url', '')
    enable_push = data.get('enable_push', True)

    logger.info(f"收到下载请求: username={username}, type={download_type}, count={count}")

    if not username and download_type != 'single':
        logger.warning("下载请求失败: 用户名为空")
        return jsonify({'error': '用户名不能为空'}), 400

    # 创建任务
    task_id_counter += 1
    task_id = f"task_{task_id_counter}"

    download_tasks[task_id] = {
        'id': task_id,
        'username': username,
        'status': 'pending',
        'progress': 0,
        'total': 0,
        'message': '准备中...',
        'created_at': datetime.now().isoformat(),
    }

    logger.info(f"创建下载任务: {task_id}")

    # 后台执行下载
    thread = threading.Thread(
        target=_execute_download,
        args=(task_id, username, download_type, count, start_pos, end_pos, position, url, enable_push)
    )
    thread.daemon = True
    thread.start()

    return jsonify({'task_id': task_id, 'message': '任务已创建'})


def _execute_download(task_id, username, download_type, count, start_pos, end_pos, position, url, enable_push):
    """执行下载任务（后台线程）"""
    try:
        logger.info(f"[{task_id}] 开始执行下载任务")
        download_tasks[task_id]['status'] = 'running'
        download_tasks[task_id]['message'] = '正在获取帖子链接...'
        socketio.emit('task_update', download_tasks[task_id])

        logger.info(f"[{task_id}] 下载参数: username={username}, type={download_type}, count={count}, range={start_pos}-{end_pos}, position={position}")

        # 获取链接
        if download_type == 'single':
            if url.startswith('http'):
                urls = [url]
            else:
                urls = [f"https://www.instagram.com/p/{url}/"]
            username = get_shortcode_from_url(urls[0]) or 'single_post'
        elif download_type == 'range':
            all_urls = fetch_post_urls(username, end_pos)
            urls = all_urls[start_pos - 1:end_pos]
        elif download_type == 'position':
            all_urls = fetch_post_urls(username, position)
            if position <= len(all_urls):
                urls = [all_urls[position - 1]]
            else:
                raise Exception(f'该账号只有 {len(all_urls)} 条帖子')
        else:  # latest
            urls = fetch_post_urls(username, count)

        logger.info(f"[{task_id}] 获取到 {len(urls)} 条链接")

        download_tasks[task_id]['total'] = len(urls)
        download_tasks[task_id]['message'] = f'开始下载 {len(urls)} 个帖子...'
        socketio.emit('task_update', download_tasks[task_id])

        def _on_progress(progress, total, message):
            download_tasks[task_id]['progress'] = progress
            download_tasks[task_id]['total'] = total
            download_tasks[task_id]['message'] = message
            socketio.emit('task_update', download_tasks[task_id])

        # 获取 Telegram 配置（仅在启用推送时）
        tg_config = None
        push_mode = 'none'

        if enable_push:
            if config and config.telegram_enabled:
                tg_config = (config.telegram_token, config.telegram_chat_id)
                push_mode = config.telegram_push_mode
            else:
                tg_data = load_tg_config()
                if tg_data:
                    tg_config = tg_data
                    push_mode = 'batch'

        # 下载
        download_selected_posts(
            urls,
            username,
            tg_config=tg_config,
            push_mode=push_mode,
            progress_callback=_on_progress,
        )

        # 保存用户到历史
        save_downloaded_user(username)

        download_tasks[task_id]['status'] = 'completed'
        download_tasks[task_id]['progress'] = len(urls)
        download_tasks[task_id]['message'] = '下载完成！'
        socketio.emit('task_update', download_tasks[task_id])
        logger.info(f"[{task_id}] 下载任务完成")

    except Exception as e:
        logger.error(f"[{task_id}] 下载任务失败: {str(e)}", exc_info=True)
        download_tasks[task_id]['status'] = 'failed'
        download_tasks[task_id]['message'] = f'下载失败: {str(e)}'
        socketio.emit('task_update', download_tasks[task_id])


@app.route('/api/tasks', methods=['GET'])
def get_tasks():
    """获取所有任务状态"""
    tasks = list(download_tasks.values())
    tasks.sort(key=lambda x: x['created_at'], reverse=True)
    return jsonify({'tasks': tasks})


@app.route('/api/tasks/<task_id>', methods=['GET'])
def get_task(task_id):
    """获取单个任务状态"""
    task = download_tasks.get(task_id)
    if not task:
        return jsonify({'error': '任务不存在'}), 404
    return jsonify(task)


# ─────────────────────────────────────────────
# 监控 API
# ─────────────────────────────────────────────

@app.route('/api/monitor/status', methods=['GET'])
def get_monitor_status():
    """获取监控状态"""
    history = load_monitor_history()
    favorite_users = config.favorite_users if config else []

    users_status = []
    for username in favorite_users:
        user_data = history.get(username, {})
        users_status.append({
            'username': username,
            'last_check': user_data.get('last_check_time', '从未检查'),
            'last_shortcode': user_data.get('last_shortcode', '-'),
        })

    return jsonify({'users': users_status})


@app.route('/api/monitor/check', methods=['POST'])
def manual_check():
    """手动触发监控检查"""
    data = request.json
    username = data.get('username', '').strip()

    logger.info(f"手动检查新帖子: username={username}")

    if not username:
        logger.warning("检查失败: 用户名为空")
        return jsonify({'error': '用户名不能为空'}), 400

    try:
        new_count, latest_shortcode = check_new_posts(username)
        logger.info(f"检查完成: username={username}, new_count={new_count}")
        return jsonify({
            'username': username,
            'new_count': new_count,
            'latest_shortcode': latest_shortcode,
            'message': f'检查完成，发现 {new_count} 条新帖子' if new_count > 0 else '没有新帖子'
        })
    except Exception as e:
        logger.error(f"检查失败: username={username}, error={str(e)}", exc_info=True)
        return jsonify({'error': str(e)}), 500


# ─────────────────────────────────────────────
# 配置 API
# ─────────────────────────────────────────────

@app.route('/api/config/telegram', methods=['GET'])
def get_telegram_config():
    """获取 Telegram 配置"""
    tg_data = load_tg_config()
    if tg_data:
        token, chat_id = tg_data
        return jsonify({
            'configured': True,
            'chat_id': chat_id,
            'token_preview': token[:10] + '...' if len(token) > 10 else token
        })
    return jsonify({'configured': False})


@app.route('/api/config/telegram', methods=['POST'])
def save_telegram_config():
    """保存 Telegram 配置"""
    data = request.json
    token = data.get('token', '').strip()
    chat_id = data.get('chat_id', '').strip()

    logger.info("保存 Telegram 配置")

    if not token or not chat_id:
        logger.warning("配置保存失败: Token 或 Chat ID 为空")
        return jsonify({'error': 'Token 和 Chat ID 不能为空'}), 400

    # 测试配置
    if send_message(token, chat_id, '✅ IG 爬虫 Web UI - Telegram 配置测试成功！'):
        save_tg_config(token, chat_id)
        logger.info("Telegram 配置保存成功")
        return jsonify({'message': '配置保存成功，测试消息已发送'})
    else:
        logger.error("Telegram 配置测试失败")
        return jsonify({'error': '配置测试失败，请检查 Token 和 Chat ID'}), 400


# ─────────────────────────────────────────────
# 文件浏览 API
# ─────────────────────────────────────────────

@app.route('/api/downloads', methods=['GET'])
def list_downloads():
    """列出下载的文件"""
    base_dir = config.download_base_dir if config else 'downloads'
    downloads_path = Path(base_dir)

    if not downloads_path.exists():
        return jsonify({'folders': []})

    folders = []
    for user_dir in downloads_path.iterdir():
        if user_dir.is_dir():
            files = list(user_dir.glob('*'))
            media_files = [f for f in files if f.suffix.lower() in {'.jpg', '.jpeg', '.png', '.mp4', '.mov'}]
            folders.append({
                'username': user_dir.name,
                'file_count': len(media_files),
                'size_mb': sum(f.stat().st_size for f in media_files) / (1024 * 1024)
            })

    folders.sort(key=lambda x: x['username'])
    return jsonify({'folders': folders})


@app.route('/api/downloads/<username>', methods=['GET'])
def get_user_files(username):
    """获取指定用户的文件列表"""
    base_dir = config.download_base_dir if config else 'downloads'
    user_dir = Path(base_dir) / username

    if not user_dir.exists():
        return jsonify({'error': '用户目录不存在'}), 404

    files = []
    for file_path in user_dir.glob('*'):
        if file_path.is_file():
            ext = file_path.suffix.lower()
            if ext in {'.jpg', '.jpeg', '.png', '.webp'}:
                file_type = 'image'
            elif ext in {'.mp4', '.mov'}:
                file_type = 'video'
            else:
                continue

            # 尝试从文件名提取 shortcode
            filename = file_path.name
            shortcode = filename.split('_')[0] if '_' in filename else filename

            files.append({
                'filename': filename,
                'type': file_type,
                'shortcode': shortcode,
                'size': file_path.stat().st_size
            })

    files.sort(key=lambda x: x['filename'])
    return jsonify({'files': files})


@app.route('/downloads/<path:filename>')
def serve_download(filename):
    """提供下载文件访问"""
    base_dir = config.download_base_dir if config else 'downloads'
    return send_from_directory(base_dir, filename)


# ─────────────────────────────────────────────
# 启动服务
# ─────────────────────────────────────────────

if __name__ == '__main__':
    import socket
    hostname = socket.gethostname()
    local_ip = socket.gethostbyname(hostname)

    print("=" * 50)
    print("   IG 爬虫 Web UI")
    print("=" * 50)
    print("\n🌐 本地访问: http://localhost:5000")
    print(f"📱 手机访问: http://192.168.5.31:5000")
    print("按 Ctrl+C 停止服务\n")

    socketio.run(app, host='0.0.0.0', port=5000, debug=False, allow_unsafe_werkzeug=True)
