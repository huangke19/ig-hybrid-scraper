#!/bin/bash
# IG 爬虫统一命令入口
# 用法：
#   ./ig run              运行单次下载
#   ./ig web              启动 Web UI（后台）
#   ./ig web stop         停止 Web UI
#   ./ig web restart      重启 Web UI
#   ./ig bot              启动 Telegram Bot（后台）
#   ./ig bot stop         停止 Telegram Bot
#   ./ig bot restart      重启 Telegram Bot
#   ./ig status           查看所有服务状态

set -e
SCRIPT_DIR="$(cd "$(dirname "$(readlink -f "$0" || echo "$0")")" && pwd)"
cd "$SCRIPT_DIR"

# FastAPI 版本
FASTAPI_PID_FILE="uvicorn.pid"
FASTAPI_LOG_FILE="fastapi.log"
# Bot API 版
BOT_API_PID_FILE="telegram_bot_api.pid"
BOT_API_LOG_FILE="telegram_bot_api.log"
# Monitor 版
MONITOR_PID_FILE="monitor.pid"
MONITOR_LOG_FILE="monitor_go.log"
MONITOR_BIN="monitor_go/ig_monitor"

if [ -d ".venv" ]; then
    source .venv/bin/activate
fi

is_fastapi_running() {
    [ -f "$FASTAPI_PID_FILE" ] && kill -0 "$(cat "$FASTAPI_PID_FILE")" 2>/dev/null
}

is_bot_api_running() {
    [ -f "$BOT_API_PID_FILE" ] && kill -0 "$(cat "$BOT_API_PID_FILE")" 2>/dev/null
}

is_monitor_running() {
    [ -f "$MONITOR_PID_FILE" ] && kill -0 "$(cat "$MONITOR_PID_FILE")" 2>/dev/null
}

show_status() {
    echo "📊 服务状态："

    # Web UI 状态
    if is_fastapi_running; then
        echo "  🌐 Web UI: ✅ 运行中（PID: $(cat "$FASTAPI_PID_FILE")）"
        echo "     访问: http://localhost:8000"
        echo "     文档: http://localhost:8000/docs"
    else
        echo "  🌐 Web UI: ⭕ 未运行"
    fi

    # Bot 状态
    if is_bot_api_running; then
        echo "  🤖 Telegram Bot: ✅ 运行中（PID: $(cat "$BOT_API_PID_FILE")）"
    else
        echo "  🤖 Telegram Bot: ⭕ 未运行"
    fi

    # Monitor 状态
    if is_monitor_running; then
        echo "  👁️  Monitor: ✅ 运行中（PID: $(cat "$MONITOR_PID_FILE")）"
    else
        echo "  👁️  Monitor: ⭕ 未运行"
    fi
}

start_fastapi() {
    if is_fastapi_running; then
        echo "⚠️  Web UI 已在运行，请先停止"
        return 1
    fi

    echo "🚀 启动 Web UI..."
    nohup uvicorn web_app_fastapi:app --host 0.0.0.0 --port 8000 > "$FASTAPI_LOG_FILE" 2>&1 &
    echo $! > "$FASTAPI_PID_FILE"
    sleep 1

    if is_fastapi_running; then
        echo "✅ Web UI 启动成功（PID: $(cat "$FASTAPI_PID_FILE")）"
        echo "🌐 访问: http://localhost:8000"
        echo "📚 API 文档: http://localhost:8000/docs"
    else
        echo "❌ 启动失败，请查看日志：$FASTAPI_LOG_FILE"
        exit 1
    fi
}

stop_web() {
    if is_fastapi_running; then
        pid=$(cat "$FASTAPI_PID_FILE")
        echo "🛑 停止 Web UI（PID: $pid）..."
        kill "$pid" 2>/dev/null || true
        rm -f "$FASTAPI_PID_FILE"
        echo "✅ Web UI 已停止"
    else
        echo "ℹ️  Web UI 未在运行"
    fi
}

start_bot_api() {
    if is_bot_api_running; then
        echo "⚠️  Telegram Bot 已在运行，请先停止"
        return 1
    fi

    echo "🤖 启动 Telegram Bot（独立模式）..."
    nohup python telegram_command_bot_standalone.py > "$BOT_API_LOG_FILE" 2>&1 &
    echo $! > "$BOT_API_PID_FILE"
    sleep 1

    if is_bot_api_running; then
        echo "✅ Telegram Bot 启动成功（PID: $(cat "$BOT_API_PID_FILE")）"
        echo "💡 独立运行，无需 Web UI"
    else
        echo "❌ 启动失败，请查看日志：$BOT_API_LOG_FILE"
        exit 1
    fi
}

stop_bot() {
    if is_bot_api_running; then
        pid=$(cat "$BOT_API_PID_FILE")
        echo "🛑 停止 Telegram Bot（PID: $pid）..."
        kill -TERM "$pid" 2>/dev/null || true
        sleep 1
        kill -0 "$pid" 2>/dev/null && kill -KILL "$pid" 2>/dev/null || true
        rm -f "$BOT_API_PID_FILE"
        echo "✅ Telegram Bot 已停止"
    else
        echo "ℹ️  Telegram Bot 未在运行"
    fi
}

start_monitor() {
    if is_monitor_running; then
        echo "⚠️  Monitor 已在运行，请先停止"
        return 1
    fi

    # 检查 cookies.json 是否需要更新
    if [ ! -f cookies.json ] || [ cookies.pkl -nt cookies.json ]; then
        echo "🔄 更新 Cookie..."
        python convert_cookies.py || {
            echo "❌ Cookie 转换失败"
            exit 1
        }
    fi

    echo "👁️  启动 Monitor（Go 版本）..."
    nohup ./"$MONITOR_BIN" > /dev/null 2>&1 &
    echo $! > "$MONITOR_PID_FILE"
    sleep 2

    if is_monitor_running; then
        echo "✅ Monitor 启动成功（PID: $(cat "$MONITOR_PID_FILE")）"
        echo "📝 日志: $MONITOR_LOG_FILE"
    else
        echo "❌ 启动失败，请查看日志：$MONITOR_LOG_FILE"
        exit 1
    fi
}

stop_monitor() {
    if is_monitor_running; then
        pid=$(cat "$MONITOR_PID_FILE")
        echo "🛑 停止 Monitor（PID: $pid）..."
        kill -TERM "$pid" 2>/dev/null || true
        sleep 1
        kill -0 "$pid" 2>/dev/null && kill -KILL "$pid" 2>/dev/null || true
        rm -f "$MONITOR_PID_FILE"
        echo "✅ Monitor 已停止"
    else
        echo "ℹ️  Monitor 未在运行"
    fi
}

case "$1" in
    run)
        python3 scraper.py
        ;;
    web)
        case "$2" in
            stop)
                stop_web
                ;;
            restart)
                stop_web
                sleep 1
                start_fastapi
                ;;
            log)
                if is_fastapi_running; then
                    tail -f "$FASTAPI_LOG_FILE"
                else
                    echo "Web UI 未运行"
                fi
                ;;
            *)
                start_fastapi
                ;;
        esac
        ;;
    bot)
        case "$2" in
            stop)
                stop_bot
                ;;
            restart)
                stop_bot
                sleep 1
                start_bot_api
                ;;
            log)
                if is_bot_api_running; then
                    tail -f "$BOT_API_LOG_FILE"
                else
                    echo "Bot 未运行"
                fi
                ;;
            *)
                start_bot_api
                ;;
        esac
        ;;
    monitor)
        case "$2" in
            stop)
                stop_monitor
                ;;
            restart)
                stop_monitor
                sleep 1
                start_monitor
                ;;
            log)
                if is_monitor_running; then
                    tail -f "$MONITOR_LOG_FILE"
                else
                    echo "Monitor 未运行"
                fi
                ;;
            *)
                start_monitor
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
        echo "  ig web                  启动 Web UI（端口 8000）"
        echo "  ig web stop             停止 Web UI"
        echo "  ig web restart          重启 Web UI"
        echo "  ig web log              查看 Web UI 实时日志"
        echo "  ig bot                  启动 Telegram Bot"
        echo "  ig bot stop             停止 Telegram Bot"
        echo "  ig bot restart          重启 Telegram Bot"
        echo "  ig bot log              查看 Bot 实时日志"
        echo "  ig monitor              启动 Instagram 监控"
        echo "  ig monitor stop         停止监控"
        echo "  ig monitor restart      重启监控"
        echo "  ig monitor log          查看监控实时日志"
        echo "  ig status               查看所有服务状态"
        echo ""
        show_status
        ;;
esac
