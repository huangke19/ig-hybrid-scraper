package main

import (
	"context"
	"encoding/json"
	"fmt"
	"log"
	"net/http"
	"os"
	"strings"
	"time"

	"github.com/chromedp/cdproto/network"
	"github.com/chromedp/chromedp"
)

const (
	targetUser           = "jadeuly713"
	checkIntervalMinutes = 30
	stateFile            = "monitor_state.json"
	cookiesFile          = "cookies.json"
	tgConfigFile         = "tg_config.json"
	logFile              = "monitor_go.log"
)

type Cookie struct {
	Name     string `json:"name"`
	Value    string `json:"value"`
	Domain   string `json:"domain"`
	Path     string `json:"path"`
	Secure   bool   `json:"secure"`
	HTTPOnly bool   `json:"httpOnly"`
	SameSite string `json:"sameSite"`
}

type MonitorState struct {
	LastShortcode string `json:"last_shortcode"`
	LastCheck     string `json:"last_check"`
}

type TgConfig struct {
	BotToken string `json:"bot_token"`
	ChatID   string `json:"chat_id"`
}

func logMsg(msg string) {
	timestamp := time.Now().Format("2006-01-02 15:04:05")
	logLine := fmt.Sprintf("[%s] %s", timestamp, msg)
	fmt.Println(logLine)

	f, err := os.OpenFile(logFile, os.O_CREATE|os.O_APPEND|os.O_WRONLY, 0644)
	if err == nil {
		defer f.Close()
		f.WriteString(logLine + "\n")
	}
}

func sendTelegram(tgConfig *TgConfig, message string) error {
	url := fmt.Sprintf("https://api.telegram.org/bot%s/sendMessage", tgConfig.BotToken)
	payload := map[string]string{
		"chat_id":    tgConfig.ChatID,
		"text":       message,
		"parse_mode": "HTML",
	}

	data, _ := json.Marshal(payload)
	resp, err := http.Post(url, "application/json", strings.NewReader(string(data)))
	if err != nil {
		return err
	}
	defer resp.Body.Close()

	return nil
}

func loadCookies() ([]*network.CookieParam, error) {
	data, err := os.ReadFile(cookiesFile)
	if err != nil {
		return nil, err
	}

	var cookies []Cookie
	if err := json.Unmarshal(data, &cookies); err != nil {
		return nil, err
	}

	var cookieParams []*network.CookieParam
	for _, c := range cookies {
		sameSite := network.CookieSameSiteNone
		switch c.SameSite {
		case "Lax":
			sameSite = network.CookieSameSiteLax
		case "Strict":
			sameSite = network.CookieSameSiteStrict
		}

		cookieParams = append(cookieParams, &network.CookieParam{
			Name:     c.Name,
			Value:    c.Value,
			Domain:   c.Domain,
			Path:     c.Path,
			Secure:   c.Secure,
			HTTPOnly: c.HTTPOnly,
			SameSite: sameSite,
		})
	}

	return cookieParams, nil
}

func getLatestShortcode(ctx context.Context) (string, error) {
	url := fmt.Sprintf("https://www.instagram.com/%s/", targetUser)

	var shortcode string
	err := chromedp.Run(ctx,
		chromedp.Navigate(url),
		chromedp.Sleep(5*time.Second),
		chromedp.Evaluate(`
			(() => {
				const links = document.querySelectorAll('a[href*="/p/"]');
				if (links.length > 0) {
					const match = links[0].href.match(/\/p\/([^\/]+)/);
					return match ? match[1] : '';
				}
				return '';
			})()
		`, &shortcode),
	)

	if err != nil {
		return "", err
	}

	if shortcode == "" {
		return "", fmt.Errorf("无法提取 shortcode")
	}

	return shortcode, nil
}

func checkForNewPosts(ctx context.Context, tgConfig *TgConfig) error {
	// 加载 Cookie
	cookies, err := loadCookies()
	if err != nil {
		return fmt.Errorf("加载 Cookie 失败: %w", err)
	}

	// 设置 Cookie
	if err := chromedp.Run(ctx,
		chromedp.Navigate("https://www.instagram.com/"),
		chromedp.ActionFunc(func(ctx context.Context) error {
			return network.SetCookies(cookies).Do(ctx)
		}),
	); err != nil {
		return err
	}

	// 获取最新帖子
	latestShortcode, err := getLatestShortcode(ctx)
	if err != nil {
		logMsg(fmt.Sprintf("获取帖子失败: %v", err))

		// 检查是否 Cookie 过期
		var pageSource string
		chromedp.Run(ctx, chromedp.OuterHTML("html", &pageSource))
		if strings.Contains(pageSource, "login") || strings.Contains(pageSource, "Log In") {
			msg := "⚠️ Instagram Cookie 已过期，请重新登录"
			logMsg(msg)
			sendTelegram(tgConfig, msg)
		}

		return err
	}

	logMsg(fmt.Sprintf("最新帖子: %s", latestShortcode))

	// 读取状态文件
	var state MonitorState
	stateData, err := os.ReadFile(stateFile)
	if err == nil {
		json.Unmarshal(stateData, &state)
	}

	// 对比是否有新帖子
	if state.LastShortcode != "" && state.LastShortcode != latestShortcode {
		now := time.Now().Format("2006-01-02 15:04:05")
		message := fmt.Sprintf(
			"🆕 <b>Instagram 新帖子提醒</b>\n\n• @%s: 1 条新帖子\n\n⏰ %s",
			targetUser, now,
		)

		logMsg("发现新帖子，发送通知")
		sendTelegram(tgConfig, message)
	} else if state.LastShortcode == "" {
		logMsg("首次运行，初始化状态")
	}

	// 更新状态文件
	newState := MonitorState{
		LastShortcode: latestShortcode,
		LastCheck:     time.Now().Format(time.RFC3339),
	}
	stateJSON, _ := json.MarshalIndent(newState, "", "  ")
	os.WriteFile(stateFile, stateJSON, 0644)

	return nil
}

func main() {
	logMsg("🚀 Instagram 监控程序启动")

	// 读取 Telegram 配置
	tgData, err := os.ReadFile(tgConfigFile)
	if err != nil {
		log.Fatalf("读取 Telegram 配置失败: %v", err)
	}

	var tgConfig TgConfig
	if err := json.Unmarshal(tgData, &tgConfig); err != nil {
		log.Fatalf("解析 Telegram 配置失败: %v", err)
	}

	// 发送启动通知
	startMsg := fmt.Sprintf(
		"🎉 <b>监控已启动</b>\n\n监控用户: @%s\n检查间隔: %d 分钟",
		targetUser, checkIntervalMinutes,
	)
	sendTelegram(&tgConfig, startMsg)
	logMsg("启动通知已发送")

	// 初始化 Chrome
	opts := append(chromedp.DefaultExecAllocatorOptions[:],
		chromedp.Flag("headless", true),
		chromedp.Flag("disable-gpu", true),
		chromedp.Flag("no-sandbox", true),
		chromedp.Flag("disable-dev-shm-usage", true),
		chromedp.UserAgent("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"),
	)

	allocCtx, cancel := chromedp.NewExecAllocator(context.Background(), opts...)
	defer cancel()

	ctx, cancel := chromedp.NewContext(allocCtx)
	defer cancel()

	logMsg("浏览器初始化成功")

	// 主循环
	for {
		logMsg(fmt.Sprintf("开始检查 @%s", targetUser))

		if err := checkForNewPosts(ctx, &tgConfig); err != nil {
			logMsg(fmt.Sprintf("检查失败: %v", err))

			// 重试一次
			logMsg("1 秒后重试...")
			time.Sleep(1 * time.Second)

			if err := checkForNewPosts(ctx, &tgConfig); err != nil {
				logMsg(fmt.Sprintf("重试失败: %v", err))
			}
		} else {
			logMsg("检查完成")
		}

		logMsg(fmt.Sprintf("等待 %d 分钟后继续检查", checkIntervalMinutes))
		time.Sleep(time.Duration(checkIntervalMinutes) * time.Minute)
	}
}
