#!/bin/bash

# Telegram Bot 启动脚本 - 支持旧版/API版 切换

show_menu() {
    echo "================================"
    echo "   Telegram Bot 启动器"
    echo "================================"
    echo "1) 旧版 Bot (直接调用 scraper)"
    echo "2) API 版 Bot (调用 FastAPI)"
    echo "3) 停止 Bot"
    echo "4) 退出"
    echo "================================"
}

start_old_bot() {
    echo "🚀 启动旧版 Bot..."
    source .venv/bin/activate
    nohup python -u telegram_command_bot.py > telegram_bot_old.log 2>&1 &
    echo $! > telegram_bot_old.pid
    echo "✅ 旧版 Bot 已启动 (PID: $(cat telegram_bot_old.pid))"
}

start_api_bot() {
    echo "🚀 启动 API 版 Bot..."
    source .venv/bin/activate
    nohup python telegram_command_bot_api.py > telegram_bot_api.log 2>&1 &
    echo $! > telegram_bot_api.pid
    echo "✅ API 版 Bot 已启动 (PID: $(cat telegram_bot_api.pid))"
    echo "💡 确保 FastAPI 服务在运行 (http://localhost:8000)"
}

stop_all() {
    echo "🛑 停止所有 Bot..."

    # 停止旧版
    if [ -f telegram_bot_old.pid ]; then
        kill $(cat telegram_bot_old.pid) 2>/dev/null
        rm telegram_bot_old.pid
        echo "✅ 旧版 Bot 已停止"
    fi

    # 停止 API 版
    if [ -f telegram_bot_api.pid ]; then
        kill $(cat telegram_bot_api.pid) 2>/dev/null
        rm telegram_bot_api.pid
        echo "✅ API 版 Bot 已停止"
    fi

    # 兜底：通过进程名查找
    pkill -f "telegram_command_bot.py" 2>/dev/null
    pkill -f "telegram_command_bot_api.py" 2>/dev/null
}

# 主逻辑
if [ "$1" == "stop" ]; then
    stop_all
    exit 0
fi

if [ "$1" == "old" ]; then
    stop_all
    start_old_bot
    exit 0
fi

if [ "$1" == "api" ]; then
    stop_all
    start_api_bot
    exit 0
fi

# 交互式菜单
while true; do
    show_menu
    read -p "请选择 [1-4]: " choice

    case $choice in
        1)
            stop_all
            start_old_bot
            break
            ;;
        2)
            stop_all
            start_api_bot
            break
            ;;
        3)
            stop_all
            break
            ;;
        4)
            echo "👋 再见！"
            exit 0
            ;;
        *)
            echo "❌ 无效选择，请重新输入"
            ;;
    esac
done
