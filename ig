#!/bin/bash
# IG 爬虫统一命令入口
# 用法：
#   ./ig run          运行单次下载
#   ./ig web          启动 Web UI（后台）
#   ./ig web stop     停止 Web UI
#   ./ig web restart  重启 Web UI
#   ./ig bot          启动 Telegram Bot（后台）
#   ./ig bot stop     停止 Telegram Bot
#   ./ig bot restart  重启 Telegram Bot
#   ./ig status       查看所有服务状态

set -e
SCRIPT_DIR="$(cd "$(dirname "$(readlink -f "$0" || echo "$0")")" && pwd)"
cd "$SCRIPT_DIR"

PID_FILE="gunicorn.pid"
BOT_PID_FILE="telegram_bot.pid"
BOT_LOG_FILE="telegram_bot.log"

if [ -d ".venv" ]; then
    source .venv/bin/activate
fi

is_web_running() {
    [ -f "$PID_FILE" ] && kill -0 "$(cat "$PID_FILE")" 2>/dev/null
}

is_bot_running() {
    [ -f "$BOT_PID_FILE" ] && kill -0 "$(cat "$BOT_PID_FILE")" 2>/dev/null
}

show_status() {
    echo "📊 服务状态："
    if is_web_running; then
        echo "  🌐 Web UI: ✅ 运行中（PID: $(cat "$PID_FILE")）"
        echo "     访问: http://localhost:5000"
    else
        echo "  🌐 Web UI: ⭕ 未运行"
    fi

    if is_bot_running; then
        echo "  🤖 Telegram Bot: ✅ 运行中（PID: $(cat "$BOT_PID_FILE")）"
    else
        echo "  🤖 Telegram Bot: ⭕ 未运行"
    fi
}

start_bot() {
    if is_bot_running; then
        echo "⚠️  Telegram Bot 已在运行（PID: $(cat "$BOT_PID_FILE")）"
        return 0
    fi

    echo "🤖 启动 Telegram Bot（后台，防休眠）..."
    nohup caffeinate -s python -u telegram_command_bot.py > "$BOT_LOG_FILE" 2>&1 &
    echo $! > "$BOT_PID_FILE"
    sleep 1

    if is_bot_running; then
        echo "✅ Telegram Bot 启动成功（PID: $(cat "$BOT_PID_FILE")）"
        echo "💡 系统将保持唤醒状态，直到 Bot 停止"
    else
        echo "❌ 启动失败，请查看日志：$BOT_LOG_FILE"
        exit 1
    fi
}

stop_bot() {
    if ! is_bot_running; then
        echo "ℹ️  Telegram Bot 未在运行"
        [ -f "$BOT_PID_FILE" ] && rm -f "$BOT_PID_FILE"
        return 0
    fi

    pid=$(cat "$BOT_PID_FILE")
    echo "🛑 正在停止 Telegram Bot（PID: $pid）..."
    kill -TERM "$pid" 2>/dev/null || true
    sleep 1

    if kill -0 "$pid" 2>/dev/null; then
        kill -KILL "$pid" 2>/dev/null || true
    fi

    rm -f "$BOT_PID_FILE"
    echo "✅ Telegram Bot 已停止"
}

case "$1" in
    run)
        python3 scraper.py
        ;;
    web)
        ./web "$2"
        ;;
    bot)
        case "$2" in
            stop)
                stop_bot
                ;;
            restart)
                stop_bot
                start_bot
                ;;
            log)
                tail -f "$BOT_LOG_FILE"
                ;;
            *)
                start_bot
                ;;
        esac
        ;;
    status)
        show_status
        ;;
    *)
        echo "IG 爬虫命令工具"
        echo ""
        echo "用法："
        echo "  ig run              运行单次下载"
        echo "  ig web              启动 Web UI（后台）"
        echo "  ig web stop         停止 Web UI"
        echo "  ig web restart      重启 Web UI"
        echo "  ig web log          查看 Web UI 实时日志"
        echo "  ig bot              启动 Telegram Bot（后台）"
        echo "  ig bot stop         停止 Telegram Bot"
        echo "  ig bot restart      重启 Telegram Bot"
        echo "  ig bot log          查看 Bot 实时日志"
        echo "  ig status           查看所有服务状态"
        echo ""
        show_status
        ;;
esac
