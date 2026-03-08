// ─────────────────────────────────────────────
// 全局变量
// ─────────────────────────────────────────────

let selectedUsername = '';
let taskRefreshInterval = null;
let taskCache = [];

// ─────────────────────────────────────────────
// 工具函数
// ─────────────────────────────────────────────

function showToast(message, type = 'success') {
    const toast = document.getElementById('toast');
    toast.textContent = message;
    toast.className = `toast ${type} show`;

    setTimeout(() => {
        toast.classList.remove('show');
    }, 3000);
}

function formatDate(isoString) {
    const date = new Date(isoString);
    return date.toLocaleString('zh-CN');
}

// ─────────────────────────────────────────────
// Tab 切换
// ─────────────────────────────────────────────

document.querySelectorAll('.tab-btn').forEach(btn => {
    btn.addEventListener('click', () => {
        const tabName = btn.dataset.tab;

        // 切换按钮状态
        document.querySelectorAll('.tab-btn').forEach(b => b.classList.remove('active'));
        btn.classList.add('active');

        // 切换内容
        document.querySelectorAll('.tab-content').forEach(content => {
            content.classList.remove('active');
        });
        document.getElementById(`${tabName}-tab`).classList.add('active');

        // 加载对应数据
        if (tabName === 'download') {
            loadUsers();
            loadTasks();
        } else if (tabName === 'config') {
            loadTelegramConfig();
            loadBotStatus();
        } else if (tabName === 'files') {
            loadFiles();
        }
    });
});

// ─────────────────────────────────────────────
// 下载管理
// ─────────────────────────────────────────────

async function loadUsers() {
    try {
        const response = await fetch('/api/users');
        const data = await response.json();

        const userList = document.getElementById('user-list');

        if (data.users.length === 0) {
            userList.innerHTML = '<div class="empty-state">暂无用户</div>';
            return;
        }

        userList.innerHTML = data.users.map(user => `
            <div class="user-chip ${user.type}" data-username="${user.username}">
                ${user.username}
            </div>
        `).join('');

        // 绑定点击事件
        document.querySelectorAll('.user-chip').forEach(chip => {
            chip.addEventListener('click', () => {
                document.querySelectorAll('.user-chip').forEach(c => c.classList.remove('selected'));
                chip.classList.add('selected');
                selectedUsername = chip.dataset.username;
                document.getElementById('custom-username').value = '';
                document.getElementById('custom-username').style.display = 'none';
            });
        });
    } catch (error) {
        showToast('加载用户列表失败', 'error');
    }
}

// 自定义用户名输入框事件
document.getElementById('custom-username').addEventListener('input', (e) => {
    if (e.target.value.trim()) {
        document.querySelectorAll('.user-chip').forEach(c => c.classList.remove('selected'));
        selectedUsername = '';
    }
});

document.getElementById('custom-username').addEventListener('focus', () => {
    document.querySelectorAll('.user-chip').forEach(c => c.classList.remove('selected'));
    selectedUsername = '';
});

// 下载类型切换
document.getElementById('download-type').addEventListener('change', (e) => {
    const type = e.target.value;

    document.getElementById('latest-options').style.display = type === 'latest' ? 'block' : 'none';
    document.getElementById('index-options').style.display = type === 'index' ? 'block' : 'none';
    document.getElementById('all-options').style.display = type === 'all' ? 'block' : 'none';
    document.getElementById('single-options').style.display = type === 'single' ? 'block' : 'none';

    // single 类型不需要用户名，隐藏用户列表
    const userListGroup = document.querySelector('.form-group:has(#user-list)');
    const customUsernameInput = document.getElementById('custom-username');
    if (type === 'single') {
        if (userListGroup) userListGroup.style.display = 'none';
        customUsernameInput.style.display = 'none';
    } else {
        if (userListGroup) userListGroup.style.display = 'block';
        customUsernameInput.style.display = 'block';
    }
});

// 开始下载
document.getElementById('start-download-btn').addEventListener('click', async () => {
    const customUsername = document.getElementById('custom-username').value.trim();
    const username = customUsername || selectedUsername;
    const downloadType = document.getElementById('download-type').value;
    const enablePush = document.getElementById('enable-push').checked;

    if (!username && downloadType !== 'single') {
        showToast('请选择或输入用户名', 'error');
        return;
    }

    const payload = {
        username,
        type: downloadType,
        enable_push: enablePush
    };

    if (downloadType === 'latest') {
        payload.count = parseInt(document.getElementById('post-count').value);
    } else if (downloadType === 'index') {
        payload.index = parseInt(document.getElementById('post-index').value);
    } else if (downloadType === 'single') {
        payload.url = document.getElementById('post-url').value.trim();
        if (!payload.url) {
            showToast('请输入帖子 URL 或 shortcode', 'error');
            return;
        }
    }

    try {
        const response = await fetch('/api/download', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(payload)
        });

        const data = await response.json();

        if (response.ok) {
            showToast('任务已创建，开始下载');
            loadTasks();
        } else {
            showToast(data.error || '创建任务失败', 'error');
        }
    } catch (error) {
        showToast('网络错误', 'error');
    }
});

function renderTasks(tasks) {
    const taskList = document.getElementById('task-list');
    const activeTaskList = document.getElementById('active-task-list');

    if (!tasks || tasks.length === 0) {
        activeTaskList.innerHTML = '<div class="empty-state" style="padding: 20px;">暂无执行中的任务</div>';
        taskList.innerHTML = '<div class="empty-state">暂无任务</div>';
        stopTaskRefresh();
        return;
    }

    const activeTasks = tasks.filter(task => task.status === 'running' || task.status === 'pending');

    if (activeTasks.length === 0) {
        activeTaskList.innerHTML = '<div class="empty-state" style="padding: 20px;">暂无执行中的任务</div>';
        stopTaskRefresh();
    } else {
        activeTaskList.innerHTML = activeTasks.map(task => `
            <div class="task-item">
                <div class="task-header">
                    <div class="task-username">@${task.username}</div>
                    <div class="task-status ${task.status}">${getStatusText(task.status)}</div>
                </div>
                <div class="task-message">${task.message}</div>
                ${task.total > 0 ? `
                    <div class="task-progress">
                        <div class="task-progress-bar" style="width: ${(task.progress / task.total) * 100}%"></div>
                    </div>
                ` : ''}
            </div>
        `).join('');
    }

    taskList.innerHTML = tasks.map(task => `
        <div class="task-item">
            <div class="task-header">
                <div class="task-username">@${task.username}</div>
                <div class="task-status ${task.status}">${getStatusText(task.status)}</div>
            </div>
            <div class="task-message">${task.message}</div>
            ${task.total > 0 ? `
                <div class="task-progress">
                    <div class="task-progress-bar" style="width: ${(task.progress / task.total) * 100}%"></div>
                </div>
            ` : ''}
        </div>
    `).join('');
}

// 加载任务列表
async function loadTasks() {
    try {
        const response = await fetch('/api/tasks');
        const data = await response.json();
        taskCache = data.tasks || [];
        renderTasks(taskCache);
    } catch (error) {
        console.error('加载任务失败:', error);
    }
}

function getStatusText(status) {
    const statusMap = {
        'pending': '等待中',
        'running': '运行中',
        'completed': '已完成',
        'failed': '失败'
    };
    return statusMap[status] || status;
}

function startTaskRefresh() {
    if (taskRefreshInterval) {
        clearInterval(taskRefreshInterval);
    }

    taskRefreshInterval = setInterval(() => {
        loadTasks();
    }, 3000); // 3 秒刷新一次
}

function stopTaskRefresh() {
    if (taskRefreshInterval) {
        clearInterval(taskRefreshInterval);
        taskRefreshInterval = null;
    }
}

// ─────────────────────────────────────────────
// 配置管理
// ─────────────────────────────────────────────

async function loadTelegramConfig() {
    try {
        const response = await fetch('/api/config/telegram');
        const data = await response.json();

        const statusBox = document.getElementById('telegram-status');

        if (data.configured) {
            statusBox.className = 'status-box success';
            statusBox.innerHTML = `
                ✅ Telegram 已配置<br>
                <small>Chat ID: ${data.chat_id}</small>
            `;
        } else {
            statusBox.className = 'status-box warning';
            statusBox.innerHTML = '⚠️ 尚未配置 Telegram 推送';
        }
    } catch (error) {
        showToast('加载配置失败', 'error');
    }
}

async function loadBotStatus() {
    try {
        const response = await fetch('/api/bot/status');
        const data = await response.json();

        const statusBox = document.getElementById('bot-status');
        const startBtn = document.getElementById('start-bot-btn');
        const stopBtn = document.getElementById('stop-bot-btn');
        const restartBtn = document.getElementById('restart-bot-btn');

        if (data.running) {
            statusBox.className = 'status-box success';
            statusBox.innerHTML = `✅ Bot 运行中<br><small>PID: ${data.pid}</small>`;
            startBtn.style.display = 'none';
            stopBtn.style.display = 'inline-block';
            restartBtn.style.display = 'inline-block';
        } else {
            statusBox.className = 'status-box warning';
            statusBox.innerHTML = '⚠️ Bot 未运行';
            startBtn.style.display = 'inline-block';
            stopBtn.style.display = 'none';
            restartBtn.style.display = 'none';
        }
    } catch (error) {
        showToast('加载 Bot 状态失败', 'error');
    }
}

document.getElementById('save-telegram-btn').addEventListener('click', async () => {
    const token = document.getElementById('tg-token').value.trim();
    const chatId = document.getElementById('tg-chat-id').value.trim();

    if (!token || !chatId) {
        showToast('请填写完整信息', 'error');
        return;
    }

    try {
        const response = await fetch('/api/config/telegram', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ token, chat_id: chatId })
        });

        const data = await response.json();

        if (response.ok) {
            showToast(data.message);
            loadTelegramConfig();
            document.getElementById('tg-token').value = '';
            document.getElementById('tg-chat-id').value = '';
        } else {
            showToast(data.error || '保存失败', 'error');
        }
    } catch (error) {
        showToast('网络错误', 'error');
    }
});

document.getElementById('start-bot-btn').addEventListener('click', async () => {
    try {
        const response = await fetch('/api/bot/start', { method: 'POST' });
        const data = await response.json();

        if (response.ok) {
            showToast(data.message);
            setTimeout(loadBotStatus, 1000);
        } else {
            showToast(data.error || '启动失败', 'error');
        }
    } catch (error) {
        showToast('网络错误', 'error');
    }
});

document.getElementById('stop-bot-btn').addEventListener('click', async () => {
    try {
        const response = await fetch('/api/bot/stop', { method: 'POST' });
        const data = await response.json();

        if (response.ok) {
            showToast(data.message);
            setTimeout(loadBotStatus, 500);
        } else {
            showToast(data.error || '停止失败', 'error');
        }
    } catch (error) {
        showToast('网络错误', 'error');
    }
});

document.getElementById('restart-bot-btn').addEventListener('click', async () => {
    try {
        showToast('正在重启 Bot...', 'info');

        const stopResponse = await fetch('/api/bot/stop', { method: 'POST' });
        if (!stopResponse.ok) {
            const data = await stopResponse.json();
            showToast(data.error || '停止失败', 'error');
            return;
        }

        await new Promise(resolve => setTimeout(resolve, 1000));

        const startResponse = await fetch('/api/bot/start', { method: 'POST' });
        const data = await startResponse.json();

        if (startResponse.ok) {
            showToast('Bot 重启成功');
            setTimeout(loadBotStatus, 1000);
        } else {
            showToast(data.error || '启动失败', 'error');
        }
    } catch (error) {
        showToast('网络错误', 'error');
    }
});

// ─────────────────────────────────────────────
// 文件浏览
// ─────────────────────────────────────────────

async function loadFiles() {
    try {
        const response = await fetch('/api/downloads');
        const data = await response.json();

        const filesList = document.getElementById('files-list');

        if (data.folders.length === 0) {
            filesList.innerHTML = '<div class="empty-state">暂无下载文件</div>';
            return;
        }

        filesList.innerHTML = data.folders.map(folder => `
            <div class="file-item">
                <div class="file-info">
                    <div class="file-username">@${folder.username}</div>
                    <div class="file-meta">
                        ${folder.file_count} 个文件 | ${folder.size_mb.toFixed(2)} MB
                    </div>
                </div>
                <button class="btn btn-secondary" onclick="viewGallery('${folder.username}')">查看图片</button>
            </div>
        `).join('');
    } catch (error) {
        showToast('加载文件列表失败', 'error');
    }
}

async function viewGallery(username) {
    try {
        const response = await fetch(`/api/downloads/${username}`);
        const data = await response.json();

        if (data.files.length === 0) {
            showToast('该用户没有媒体文件', 'error');
            return;
        }

        const modal = document.getElementById('image-modal');
        const modalUsername = document.getElementById('modal-username');
        const modalGallery = document.getElementById('modal-gallery');

        modalUsername.textContent = `@${username}`;

        modalGallery.innerHTML = data.files.map((file, index) => {
            if (file.type === 'image') {
                return `
                    <div class="gallery-item">
                        <img src="/downloads/${username}/${file.filename}"
                             alt="${file.filename}"
                             loading="lazy"
                             data-index="${index}"
                             data-username="${username}"
                             onclick="openLightbox('${username}', ${index})">
                        <div class="gallery-caption">${file.shortcode || file.filename}</div>
                    </div>
                `;
            } else if (file.type === 'video') {
                return `
                    <div class="gallery-item">
                        <video onclick="openLightbox('${username}', ${index})">
                            <source src="/downloads/${username}/${file.filename}" type="video/mp4">
                        </video>
                        <div class="gallery-caption">${file.shortcode || file.filename}</div>
                    </div>
                `;
            }
            return '';
        }).join('');

        // 保存当前媒体列表到全局变量（包含图片和视频）
        window.currentGallery = {
            username: username,
            files: data.files
        };

        modal.style.display = 'flex';
    } catch (error) {
        showToast('加载图片失败', 'error');
    }
}

// 打开 Lightbox
function openLightbox(username, index) {
    const lightbox = document.getElementById('lightbox');
    const lightboxImg = document.getElementById('lightbox-img');
    const lightboxVideo = document.getElementById('lightbox-video');
    const lightboxCaption = document.querySelector('.lightbox-caption');

    const files = window.currentGallery.files;
    const file = files[index];

    // 根据文件类型显示图片或视频
    if (file.type === 'image') {
        lightboxImg.src = `/downloads/${username}/${file.filename}`;
        lightboxImg.style.display = 'block';
        lightboxVideo.style.display = 'none';
        lightboxVideo.pause();
    } else if (file.type === 'video') {
        lightboxVideo.querySelector('source').src = `/downloads/${username}/${file.filename}`;
        lightboxVideo.load();
        lightboxVideo.style.display = 'block';
        lightboxImg.style.display = 'none';
    }

    lightboxCaption.textContent = file.shortcode || file.filename;

    lightbox.style.display = 'flex';
    window.currentLightboxIndex = index;
}

// 关闭 Lightbox
document.querySelector('.lightbox-close').addEventListener('click', () => {
    const lightboxVideo = document.getElementById('lightbox-video');
    lightboxVideo.pause();
    document.getElementById('lightbox').style.display = 'none';
});

// 上一张
document.querySelector('.lightbox-prev').addEventListener('click', () => {
    if (!window.currentGallery) return;

    const files = window.currentGallery.files;
    window.currentLightboxIndex = (window.currentLightboxIndex - 1 + files.length) % files.length;

    const file = files[window.currentLightboxIndex];
    const lightboxImg = document.getElementById('lightbox-img');
    const lightboxVideo = document.getElementById('lightbox-video');
    const lightboxCaption = document.querySelector('.lightbox-caption');

    if (file.type === 'image') {
        lightboxImg.src = `/downloads/${window.currentGallery.username}/${file.filename}`;
        lightboxImg.style.display = 'block';
        lightboxVideo.style.display = 'none';
        lightboxVideo.pause();
    } else if (file.type === 'video') {
        lightboxVideo.querySelector('source').src = `/downloads/${window.currentGallery.username}/${file.filename}`;
        lightboxVideo.load();
        lightboxVideo.style.display = 'block';
        lightboxImg.style.display = 'none';
    }

    lightboxCaption.textContent = file.shortcode || file.filename;
});

// 下一张
document.querySelector('.lightbox-next').addEventListener('click', () => {
    if (!window.currentGallery) return;

    const files = window.currentGallery.files;
    window.currentLightboxIndex = (window.currentLightboxIndex + 1) % files.length;

    const file = files[window.currentLightboxIndex];
    const lightboxImg = document.getElementById('lightbox-img');
    const lightboxVideo = document.getElementById('lightbox-video');
    const lightboxCaption = document.querySelector('.lightbox-caption');

    if (file.type === 'image') {
        lightboxImg.src = `/downloads/${window.currentGallery.username}/${file.filename}`;
        lightboxImg.style.display = 'block';
        lightboxVideo.style.display = 'none';
        lightboxVideo.pause();
    } else if (file.type === 'video') {
        lightboxVideo.querySelector('source').src = `/downloads/${window.currentGallery.username}/${file.filename}`;
        lightboxVideo.load();
        lightboxVideo.style.display = 'block';
        lightboxImg.style.display = 'none';
    }

    lightboxCaption.textContent = file.shortcode || file.filename;
});

// 键盘导航
document.addEventListener('keydown', (e) => {
    const lightbox = document.getElementById('lightbox');
    if (lightbox.style.display !== 'flex') return;

    if (e.key === 'Escape') {
        const lightboxVideo = document.getElementById('lightbox-video');
        lightboxVideo.pause();
        lightbox.style.display = 'none';
    } else if (e.key === 'ArrowLeft') {
        document.querySelector('.lightbox-prev').click();
    } else if (e.key === 'ArrowRight') {
        document.querySelector('.lightbox-next').click();
    }
});

// 点击 Lightbox 背景关闭
document.getElementById('lightbox').addEventListener('click', (e) => {
    if (e.target.id === 'lightbox') {
        const lightboxVideo = document.getElementById('lightbox-video');
        lightboxVideo.pause();
        document.getElementById('lightbox').style.display = 'none';
    }
});

// 关闭模态框
document.querySelector('.modal-close').addEventListener('click', () => {
    document.getElementById('image-modal').style.display = 'none';
});

// 点击模态框外部关闭
document.getElementById('image-modal').addEventListener('click', (e) => {
    if (e.target.id === 'image-modal') {
        document.getElementById('image-modal').style.display = 'none';
    }
});

// ─────────────────────────────────────────────
// 初始化
// ─────────────────────────────────────────────

document.addEventListener('DOMContentLoaded', () => {
    loadUsers();
    loadTasks();
    startTaskRefresh();
});

// 页面卸载时停止刷新
window.addEventListener('beforeunload', () => {
    stopTaskRefresh();
});
