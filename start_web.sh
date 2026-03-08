#!/bin/bash

# IG 爬虫启动脚本 - 支持 Flask/FastAPI 切换

show_menu() {
    echo "================================"
    echo "   IG 爬虫 Web UI 启动器"
    echo "================================"
    echo "1) Flask 版本 (端口 5000)"
    echo "2) FastAPI 版本 (端口 8000)"
    echo "3) 退出"
    echo "================================"
}

start_flask() {
    echo "🚀 启动 Flask 版本..."
    source .venv/bin/activate
    gunicorn -w 4 -b 0.0.0.0:5000 web_app:app --daemon --pid gunicorn_flask.pid
    echo "✅ Flask 服务已启动 (PID: $(cat gunicorn_flask.pid))"
    echo "🌐 访问: http://localhost:5000"
}

start_fastapi() {
    echo "🚀 启动 FastAPI 版本..."
    source .venv/bin/activate
    nohup uvicorn web_app_fastapi:app --host 0.0.0.0 --port 8000 > fastapi.log 2>&1 &
    echo $! > uvicorn.pid
    echo "✅ FastAPI 服务已启动 (PID: $(cat uvicorn.pid))"
    echo "🌐 访问: http://localhost:8000"
    echo "📚 API 文档: http://localhost:8000/docs"
}

stop_all() {
    echo "🛑 停止所有服务..."

    if [ -f gunicorn_flask.pid ]; then
        kill $(cat gunicorn_flask.pid) 2>/dev/null
        rm gunicorn_flask.pid
        echo "✅ Flask 服务已停止"
    fi

    if [ -f uvicorn.pid ]; then
        kill $(cat uvicorn.pid) 2>/dev/null
        rm uvicorn.pid
        echo "✅ FastAPI 服务已停止"
    fi
}

# 主逻辑
if [ "$1" == "stop" ]; then
    stop_all
    exit 0
fi

if [ "$1" == "flask" ]; then
    stop_all
    start_flask
    exit 0
fi

if [ "$1" == "fastapi" ]; then
    stop_all
    start_fastapi
    exit 0
fi

# 交互式菜单
while true; do
    show_menu
    read -p "请选择 [1-3]: " choice

    case $choice in
        1)
            stop_all
            start_flask
            break
            ;;
        2)
            stop_all
            start_fastapi
            break
            ;;
        3)
            echo "👋 再见！"
            exit 0
            ;;
        *)
            echo "❌ 无效选择，请重新输入"
            ;;
    esac
done
