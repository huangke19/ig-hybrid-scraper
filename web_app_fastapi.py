"""
web_app_fastapi.py - IG 爬虫 Web UI (FastAPI 版本)
"""

from fastapi import FastAPI, HTTPException, BackgroundTasks
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List, Literal, Optional
from pathlib import Path
import logging
import subprocess
import os
from datetime import datetime

from scraper import (
    fetch_post_urls,
    download_selected_posts,
    load_downloaded_users,
    save_downloaded_user,
)
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
    datefmt='%Y-%m-%d %H:%M:%S',
    handlers=[
        logging.FileHandler('web_app.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

app = FastAPI(title="IG Scraper API", version="2.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

logger.info("FastAPI 应用启动")

download_tasks = {}
task_id_counter = 0


# ─────────────────────────────────────────────
# 数据模型
# ─────────────────────────────────────────────

class User(BaseModel):
    username: str
    type: Literal['favorite', 'history']

class UsersResponse(BaseModel):
    users: List[User]

class DownloadRequest(BaseModel):
    username: str = ''
    type: Literal['latest', 'all', 'index', 'single'] = 'latest'
    count: int = 10
    index: int = 1
    url: str = ''
    enable_push: bool = True

class TaskResponse(BaseModel):
    task_id: str
    message: str

class Task(BaseModel):
    id: str
    username: str
    status: Literal['pending', 'running', 'completed', 'failed']
    progress: int
    total: int
    message: str
    created_at: str

class TasksResponse(BaseModel):
    tasks: List[Task]

class TelegramConfig(BaseModel):
    token: str
    chat_id: str

class TelegramConfigResponse(BaseModel):
    configured: bool
    chat_id: Optional[str] = None
    token_preview: Optional[str] = None

class BotStatusResponse(BaseModel):
    running: bool
    pid: Optional[str] = None

class MessageResponse(BaseModel):
    message: str

class ErrorResponse(BaseModel):
    error: str

class FolderInfo(BaseModel):
    username: str
    file_count: int
    size_mb: float

class FoldersResponse(BaseModel):
    folders: List[FolderInfo]

class FileInfo(BaseModel):
    filename: str
    type: Literal['image', 'video']
    shortcode: str
    size: int

class FilesResponse(BaseModel):
    files: List[FileInfo]


# ─────────────────────────────────────────────
# 首页
# ─────────────────────────────────────────────

@app.get('/')
async def index():
    return FileResponse('templates/index.html')


# ─────────────────────────────────────────────
# 用户管理 API
# ─────────────────────────────────────────────

@app.get('/api/users', response_model=UsersResponse)
async def get_users():
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
    return {'users': users}


# ─────────────────────────────────────────────
# 下载任务 API
# ─────────────────────────────────────────────

@app.post('/api/download', response_model=TaskResponse)
async def start_download(request: DownloadRequest, background_tasks: BackgroundTasks):
    global task_id_counter

    username = request.username.strip()
    download_type = request.type
    count = request.count
    index = request.index
    url = request.url
    enable_push = request.enable_push

    logger.info(f"收到下载请求: username={username}, type={download_type}, count={count}, index={index}")

    if not username and download_type != 'single':
        logger.warning("下载请求失败: 用户名为空")
        raise HTTPException(status_code=400, detail='用户名不能为空')

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

    background_tasks.add_task(
        _execute_download,
        task_id, username, download_type, count, index, url, enable_push
    )

    return {'task_id': task_id, 'message': '任务已创建'}


async def _execute_download(task_id, username, download_type, count, index, url, enable_push):
    try:
        logger.info(f"[{task_id}] 开始执行下载任务")
        download_tasks[task_id]['status'] = 'running'
        download_tasks[task_id]['message'] = '正在获取帖子链接...'

        logger.info(f"[{task_id}] 下载参数: username={username}, type={download_type}, count={count}, index={index}, url={url}")

        if download_type == 'single':
            if url.startswith('http'):
                urls = [url]
                shortcode = get_shortcode_from_url(urls[0])
                username = shortcode if shortcode else 'single_post'
            else:
                urls = [f"https://www.instagram.com/p/{url}/"]
                shortcode = get_shortcode_from_url(urls[0])
                username = shortcode if shortcode else url[:20]
        elif download_type == 'index':
            all_urls = fetch_post_urls(username, index)
            if index <= len(all_urls):
                urls = [all_urls[index - 1]]
            else:
                raise Exception(f'该账号只有 {len(all_urls)} 条帖子，无法下载第 {index} 条')
        elif download_type == 'latest':
            urls = fetch_post_urls(username, count)
        elif download_type == 'all':
            urls = fetch_post_urls(username, 9999)
        else:
            raise Exception(f'未知的下载类型: {download_type}')

        logger.info(f"[{task_id}] 获取到 {len(urls)} 条链接")

        download_tasks[task_id]['total'] = len(urls)
        download_tasks[task_id]['message'] = f'开始下载 {len(urls)} 个帖子...'

        def _on_progress(progress, total, message):
            download_tasks[task_id]['progress'] = progress
            download_tasks[task_id]['total'] = total
            download_tasks[task_id]['message'] = message

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

        download_selected_posts(
            urls,
            username,
            tg_config=tg_config,
            push_mode=push_mode,
            progress_callback=_on_progress,
        )

        save_downloaded_user(username)

        download_tasks[task_id]['status'] = 'completed'
        download_tasks[task_id]['progress'] = len(urls)
        download_tasks[task_id]['message'] = '下载完成！'
        logger.info(f"[{task_id}] 下载任务完成")

    except Exception as e:
        logger.error(f"[{task_id}] 下载任务失败: {str(e)}", exc_info=True)
        download_tasks[task_id]['status'] = 'failed'
        download_tasks[task_id]['message'] = f'下载失败: {str(e)}'


@app.get('/api/tasks', response_model=TasksResponse)
async def get_tasks():
    tasks = list(download_tasks.values())
    tasks.sort(key=lambda x: x['created_at'], reverse=True)
    return {'tasks': tasks}


@app.get('/api/tasks/{task_id}', response_model=Task)
async def get_task(task_id: str):
    task = download_tasks.get(task_id)
    if not task:
        raise HTTPException(status_code=404, detail='任务不存在')
    return task


# ─────────────────────────────────────────────
# 配置 API
# ─────────────────────────────────────────────

@app.get('/api/config/telegram', response_model=TelegramConfigResponse)
async def get_telegram_config():
    tg_data = load_tg_config()
    if tg_data:
        token, chat_id = tg_data
        return {
            'configured': True,
            'chat_id': chat_id,
            'token_preview': token[:10] + '...' if len(token) > 10 else token
        }
    return {'configured': False}


@app.post('/api/config/telegram', response_model=MessageResponse)
async def save_telegram_config(config_data: TelegramConfig):
    token = config_data.token.strip()
    chat_id = config_data.chat_id.strip()

    logger.info("保存 Telegram 配置")

    if not token or not chat_id:
        logger.warning("配置保存失败: Token 或 Chat ID 为空")
        raise HTTPException(status_code=400, detail='Token 和 Chat ID 不能为空')

    if send_message(token, chat_id, '✅ IG 爬虫 Web UI - Telegram 配置测试成功！'):
        save_tg_config(token, chat_id)
        logger.info("Telegram 配置保存成功")
        return {'message': '配置保存成功，测试消息已发送'}
    else:
        logger.error("Telegram 配置测试失败")
        raise HTTPException(status_code=400, detail='配置测试失败，请检查 Token 和 Chat ID')


@app.get('/api/bot/status', response_model=BotStatusResponse)
async def get_bot_status():
    try:
        result = subprocess.run(['pgrep', '-f', 'telegram_command_bot.py'],
                              capture_output=True, text=True)
        running = bool(result.stdout.strip())
        pid = result.stdout.strip() if running else None
        return {'running': running, 'pid': pid}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post('/api/bot/start', response_model=MessageResponse)
async def start_bot():
    try:
        result = subprocess.run(['pgrep', '-f', 'telegram_command_bot.py'],
                              capture_output=True, text=True)
        if result.stdout.strip():
            raise HTTPException(status_code=400, detail='Bot 已在运行中')

        script_path = os.path.join(os.path.dirname(__file__), 'telegram_command_bot.py')
        process = subprocess.Popen(['python', '-u', script_path],
                        stdout=subprocess.DEVNULL,
                        stderr=subprocess.DEVNULL,
                        start_new_session=True,
                        cwd=os.path.dirname(__file__))

        pid_file = os.path.join(os.path.dirname(__file__), 'telegram_bot.pid')
        with open(pid_file, 'w') as f:
            f.write(str(process.pid))

        logger.info(f"Bot 启动成功 (PID: {process.pid})")
        return {'message': 'Bot 启动成功'}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Bot 启动失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post('/api/bot/stop', response_model=MessageResponse)
async def stop_bot():
    try:
        result = subprocess.run(['pgrep', '-f', 'telegram_command_bot.py'],
                              capture_output=True, text=True)
        pids = result.stdout.strip().split('\n')
        pids = [p for p in pids if p]

        if not pids:
            raise HTTPException(status_code=400, detail='Bot 未运行')

        for pid in pids:
            subprocess.run(['kill', pid])

        pid_file = os.path.join(os.path.dirname(__file__), 'telegram_bot.pid')
        if os.path.exists(pid_file):
            os.remove(pid_file)

        logger.info(f"Bot 已停止 (PID: {', '.join(pids)})")
        return {'message': 'Bot 已停止'}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Bot 停止失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ─────────────────────────────────────────────
# 文件浏览 API
# ─────────────────────────────────────────────

@app.get('/api/downloads', response_model=FoldersResponse)
async def list_downloads():
    base_dir = config.download_base_dir if config else 'downloads'
    downloads_path = Path(base_dir)

    if not downloads_path.exists():
        return {'folders': []}

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
    return {'folders': folders}


@app.get('/api/downloads/{username}', response_model=FilesResponse)
async def get_user_files(username: str):
    base_dir = config.download_base_dir if config else 'downloads'
    user_dir = Path(base_dir) / username

    if not user_dir.exists():
        raise HTTPException(status_code=404, detail='用户目录不存在')

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

            filename = file_path.name
            shortcode = filename.split('_')[0] if '_' in filename else filename

            files.append({
                'filename': filename,
                'type': file_type,
                'shortcode': shortcode,
                'size': file_path.stat().st_size
            })

    files.sort(key=lambda x: x['filename'])
    return {'files': files}


@app.get('/downloads/{path:path}')
async def serve_download(path: str):
    base_dir = config.download_base_dir if config else 'downloads'
    file_path = Path(base_dir) / path
    if not file_path.exists():
        raise HTTPException(status_code=404, detail='文件不存在')
    return FileResponse(file_path)


# 挂载静态文件
app.mount("/static", StaticFiles(directory="static"), name="static")


if __name__ == '__main__':
    import uvicorn
    print("=" * 50)
    print("   IG 爬虫 Web UI (FastAPI)")
    print("=" * 50)
    print("\n🌐 本地访问: http://localhost:8000")
    print("📱 手机访问: http://192.168.5.31:8000")
    print("📚 API 文档: http://localhost:8000/docs")
    print("按 Ctrl+C 停止服务\n")

    uvicorn.run(app, host='0.0.0.0', port=8000)
