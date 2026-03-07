# IG 监控脚本使用说明

## 功能说明

监控脚本会每天自动检查你关注的 Instagram 用户是否发布了新帖子，如果有新帖子会通过 Telegram 推送通知到你的手机。

## 前置条件

1. 已完成 `auth.py` 登录并保存 Cookie
2. 已配置 Telegram Bot（在 `config.yaml` 或运行 `auth.py` 时配置）
3. 在 `config.yaml` 中配置了 `favorite_users` 列表

## 使用方式

### 方式 1：手动测试（推荐先测试）

```bash
# 执行一次检查（测试用）
python monitor.py --once
```

第一次运行会记录当前状态，不会发送通知。第二次运行时如果有新帖子才会通知。

### 方式 2：持续运行（前台）

```bash
# 每 24 小时检查一次，持续运行
./monitor
```

按 `Ctrl+C` 可以停止。

### 方式 3：macOS 后台自动运行（推荐）⭐

使用 launchd 让 macOS 每天自动运行监控脚本。

#### 安装步骤：

1. 复制配置文件到 LaunchAgents 目录：
```bash
cp com.ig.monitor.plist ~/Library/LaunchAgents/
```

2. 加载配置：
```bash
launchctl load ~/Library/LaunchAgents/com.ig.monitor.plist
```

3. 验证是否加载成功：
```bash
launchctl list | grep ig.monitor
```

#### 默认设置：

- 每天上午 10:00 自动运行一次
- 日志保存在 `monitor.log` 和 `monitor.error.log`

#### 修改运行时间：

编辑 `com.ig.monitor.plist` 文件中的时间：

```xml
<key>StartCalendarInterval</key>
<dict>
    <key>Hour</key>
    <integer>10</integer>  <!-- 改成你想要的小时（0-23）-->
    <key>Minute</key>
    <integer>0</integer>   <!-- 改成你想要的分钟（0-59）-->
</dict>
```

修改后重新加载：
```bash
launchctl unload ~/Library/LaunchAgents/com.ig.monitor.plist
launchctl load ~/Library/LaunchAgents/com.ig.monitor.plist
```

#### 停止自动运行：

```bash
launchctl unload ~/Library/LaunchAgents/com.ig.monitor.plist
```

#### 查看日志：

```bash
# 查看运行日志
tail -f monitor.log

# 查看错误日志
tail -f monitor.error.log
```

## 工作原理

1. 脚本会读取 `config.yaml` 中的 `favorite_users` 列表
2. 对每个用户获取最新 20 条帖子
3. 与上次记录的最新帖子对比（记录在 `monitor_history.json`）
4. 如果发现新帖子，通过 Telegram 发送通知
5. 更新 `monitor_history.json` 记录

## 注意事项

- 第一次运行只会记录当前状态，不会发送通知
- 建议监控的用户数量不要超过 10 个（避免请求过多）
- 每天只检查一次，不会对 Instagram 造成压力
- 如果 Cookie 过期，需要重新运行 `auth.py` 登录
- 监控历史保存在 `monitor_history.json`，可以手动删除重置

## 故障排查

### 没有收到通知？

1. 检查 Telegram Bot 配置是否正确
2. 确认已向 Bot 发送过 `/start` 命令
3. 查看 `monitor.log` 日志文件
4. 手动运行 `python monitor.py --once` 测试

### Cookie 过期？

重新运行 `auth.py` 登录即可。

### 想要立即测试？

```bash
# 删除历史记录，重新检测
rm monitor_history.json
python monitor.py --once
```

## 文件说明

- `monitor.py` - 监控脚本主程序
- `monitor` - 启动脚本（自动激活虚拟环境）
- `monitor_history.json` - 监控历史记录（自动生成）
- `monitor.log` - 运行日志（自动生成）
- `monitor.error.log` - 错误日志（自动生成）
- `com.ig.monitor.plist` - macOS launchd 配置文件
