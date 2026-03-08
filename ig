#!/bin/bash
# IG 爬虫统一命令入口
# 用法：
#   ./ig run              运行单次下载
#   ./ig web [flask|fastapi]  启动 Web UI（后台）
#   ./ig web stop         停止 Web UI
#   ./ig web restart      重启 Web UI
#   ./ig bot [old|api]    启动 Telegram Bot（后台）
#   ./ig bot stop         停止 Telegram Bot
#   ./ig bot restart      重启 Telegram Bot
#   ./ig status           查看所有服务状态

set -e
SCRIPT_DIR="$(cd "$(dirname "$(readlink -f "$0" || echo "$0")")" && pwd)"
cd "$SCRIPT_DIR"

# Flask 版本
FLASK_PID_FILE="gunicorn_flask.pid"
# FastAPI 版本
FASTAPI_PID_FILE="uvicorn.pid"
FASTAPI_LOG_FILE="fastapi.log"
# Bot 旧版
BOT_OLD_PID_FILE="telegram_bot_old.pid"
BOT_OLD_LOG_FILE="telegram_bot_old.log"
# Bot API 版
BOT_API_PID_FILE="telegram_bot_api.pid"
BOT_API_LOG_FILE="telegram_bot_api.log"

if [ -d ".venv" ]; then
    source .venv/bin/activate
fi

is_flask_running() {
    [ -f "$FLASK_PID_FILE" ] && kill -0 "$(cat "$FLASK_PID_FILE")" 2>/dev/null
}

is_fastapi_running() {
    [ -f "$FASTAPI_PID_FILE" ] && kill -0 "$(cat "$FASTAPI_PID_FILE")" 2>/dev/null
}

is_bot_old_running() {
    [ -f "$BOT_OLD_PID_FILE" ] && kill -0 "$(cat "$BOT_OLD_PID_FILE")" 2>/dev/null
}

is_bot_api_running() {
    [ -f "$BOT_API_PID_FILE" ] && kill -0 "$(cat "$BOT_API_PID_FILE")" 2>/dev/null
}

show_status() {
    echo "📊 服务状态："

    # Web UI 状态
    if is_flask_running; then
        echo "  🌐 Web UI (Flask): ✅ 运行中（PID: $(cat "$FLASK_PID_FILE")）"
        echo "     访问: http://localhost:5000"
    elif is_fastapi_running; then
        echo "  🌐 Web UI (FastAPI): ✅ 运行中（PID: $(cat "$FASTAPI_PID_FILE")）"
        echo "     访问: http://localhost:8000"
        echo "     文档: http://localhost:8000/docs"
    else
        echo "  🌐 Web UI: ⭕ 未运行"
    fi

    # Bot 状态
    if is_bot_old_running; then
        echo "  🤖 Telegram Bot (旧版): ✅ 运行中（PID: $(cat "$BOT_OLD_PID_FILE")）"
    elif is_bot_api_running; then
        echo "  🤖 Telegram Bot (API版): ✅ 运行中（PID: $(cat "$BOT_API_PID_FILE")）"
    else
        echo "  🤖 Telegram Bot: ⭕ 未运行"
    fi
}

start_flask() {
    if is_flask_running || is_fastapi_running; then
        echo "⚠️  Web UI 已在运行，请先停止"
        return 1
    fi

    echo "🚀 启动 Flask 版本..."
    gunicorn -w 4 -b 0.0.0.0:5000 web_app:app --daemon --pid "$FLASK_PID_FILE"
    sleep 1

    if is_flask_running; then
        echo "✅ Flask 启动成功（PID: $(cat "$FLASK_PID_FILE")）"
        echo "🌐 访问: http://localhost:5000"
    else
        echo "❌ 启动失败"
        exit 1
    fi
}

start_fastapi() {
    if is_flask_running || is_fastapi_running; then
        echo "⚠️  Web UI 已在运行，请先停止"
        return 1
    fi

    echo "🚀 启动 FastAPI 版本..."
    nohup uvicorn web_app_fastapi:app --host 0.0.0.0 --port 8000 > "$FASTAPI_LOG_FILE" 2>&1 &
    echo $! > "$FASTAPI_PID_FILE"
    sleep 1

    if is_fastapi_running; then
        echo "✅ FastAPI 启动成功（PID: $(cat "$FASTAPI_PID_FILE")）"
        echo "🌐 访问: http://localhost:8000"
        echo "📚 API 文档: http://localhost:8000/docs"
    else
        echo "❌ 启动失败，请查看日志：$FASTAPI_LOG_FILE"
        exit 1
    fi
}

stop_web() {
    local stopped=0

    if is_flask_running; then
        pid=$(cat "$FLASK_PID_FILE")
        echo "🛑 停止 Flask（PID: $pid）..."
        kill "$pid" 2>/dev/null || true
        rm -f "$FLASK_PID_FILE"
        stopped=1
    fi

    if is_fastapi_running; then
        pid=$(cat "$FASTAPI_PID_FILE")
        echo "🛑 停止 FastAPI（PID: $pid）..."
        kill "$pid" 2>/dev/null || true
        rm -f "$FASTAPI_PID_FILE"
        stopped=1
    fi

    if [ $stopped -eq 0 ]; then
        echo "ℹ️  Web UI 未在运行"
    else
        echo "✅ Web UI 已停止"
    fi
}

start_bot_old() {
    if is_bot_old_running || is_bot_api_running; then
        echo "⚠️  Telegram Bot 已在运行，请先停止"
        return 1
    fi

    echo "🤖 启动旧版 Bot（后台，防休眠）..."
    nohup caffeinate -s python -u telegram_command_bot.py > "$BOT_OLD_LOG_FILE" 2>&1 &
    echo $! > "$BOT_OLD_PID_FILE"
    sleep 1

    if is_bot_old_running; then
        echo "✅ 旧版 Bot 启动成功（PID: $(cat "$BOT_OLD_PID_FILE")）"
        echo "💡 系统将保持唤醒状态，直到 Bot 停止"
    else
        echo "❌ 启动失败，请查看日志：$BOT_OLD_LOG_FILE"
        exit 1
    fi
}

start_bot_api() {
    if is_bot_old_running || is_bot_api_running; then
        echo "⚠️  Telegram Bot 已在运行，请先停止"
        return 1
    fi

    echo "🤖 启动 API 版 Bot（后台）..."
    nohup python telegram_command_bot_api.py > "$BOT_API_LOG_FILE" 2>&1 &
    echo $! > "$BOT_API_PID_FILE"
    sleep 1

    if is_bot_api_running; then
        echo "✅ API 版 Bot 启动成功（PID: $(cat "$BOT_API_PID_FILE")）"
        echo "💡 确保 FastAPI 服务在运行 (http://localhost:8000)"
    else
        echo "❌ 启动失败，请查看日志：$BOT_API_LOG_FILE"
        exit 1
    fi
}

stop_bot() {
    local stopped=0

    if is_bot_old_running; then
        pid=$(cat "$BOT_OLD_PID_FILE")
        echo "🛑 停止旧版 Bot（PID: $pid）..."
        kill -TERM "$pid" 2>/dev/null || true
        sleep 1
        kill -0 "$pid" 2>/dev/null && kill -KILL "$pid" 2>/dev/null || true
        rm -f "$BOT_OLD_PID_FILE"
        stopped=1
    fi

    if is_bot_api_running; then
        pid=$(cat "$BOT_API_PID_FILE")
        echo "🛑 停止 API 版 Bot（PID: $pid）..."
        kill -TERM "$pid" 2>/dev/null || true
        sleep 1
        kill -0 "$pid" 2>/dev/null && kill -KILL "$pid" 2>/dev/null || true
        rm -f "$BOT_API_PID_FILE"
        stopped=1
    fi

    if [ $stopped -eq 0 ]; then
        echo "ℹ️  Telegram Bot 未在运行"
    else
        echo "✅ Telegram Bot 已停止"
    fi
}

case "$1" in
    run)
        python3 scraper.py
        ;;
    web)
        case "$2" in
            flask)
                stop_web
                start_flask
                ;;
            fastapi)
                stop_web
                start_fastapi
                ;;
            stop)
                stop_web
                ;;
            restart)
                stop_web
                sleep 1
                start_flask
                ;;
            log)
                if is_flask_running; then
                    tail -f gunicorn.log 2>/dev/null || echo "日志文件不存在"
                elif is_fastapi_running; then
                    tail -f "$FASTAPI_LOG_FILE"
                else
                    echo "Web UI 未运行"
                fi
                ;;
            *)
                echo "请指定版本: ig web [flask|fastapi|stop|restart|log]"
                ;;
        esac
        ;;
    bot)
        case "$2" in
            old)
                stop_bot
                start_bot_old
                ;;
            api)
                stop_bot
                start_bot_api
                ;;
            stop)
                stop_bot
                ;;
            restart)
                stop_bot
                sleep 1
                start_bot_old
                ;;
            log)
                if is_bot_old_running; then
                    tail -f "$BOT_OLD_LOG_FILE"
                elif is_bot_api_running; then
                    tail -f "$BOT_API_LOG_FILE"
                else
                    echo "Bot 未运行"
                fi
                ;;
            *)
                echo "请指定版本: ig bot [old|api|stop|restart|log]"
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
        echo "  ig run                  运行单次下载"
        echo "  ig web flask            启动 Flask 版本（端口 5000）"
        echo "  ig web fastapi          启动 FastAPI 版本（端口 8000）"
        echo "  ig web stop             停止 Web UI"
        echo "  ig web restart          重启 Web UI"
        echo "  ig web log              查看 Web UI 实时日志"
        echo "  ig bot old              启动旧版 Bot（直接调用 scraper）"
        echo "  ig bot api              启动 API 版 Bot（调用 FastAPI）"
        echo "  ig bot stop             停止 Telegram Bot"
        echo "  ig bot restart          重启 Telegram Bot"
        echo "  ig bot log              查看 Bot 实时日志"
        echo "  ig status               查看所有服务状态"
        echo ""
        show_status
        ;;
esac
