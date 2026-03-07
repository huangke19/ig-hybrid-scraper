"""
utils.py - 公共工具模块
包含：浏览器初始化、Cookie 管理、URL 解析、重试装饰器、人性化延时
"""

import pickle
import random
import re
import time
import functools
import os

from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager
from requests.cookies import RequestsCookieJar


# ─────────────────────────────────────────────
# 1. 浏览器初始化
# ─────────────────────────────────────────────

def init_driver(headless: bool = False) -> webdriver.Chrome:
    """
    初始化带防检测参数的 Chrome 浏览器。
    headless=True 时以无头模式运行（适合服务器环境）。
    """
    options = webdriver.ChromeOptions()
    options.add_argument("--disable-blink-features=AutomationControlled")
    options.add_experimental_option("excludeSwitches", ["enable-automation"])
    options.add_experimental_option("useAutomationExtension", False)

    # 伪装 User-Agent，降低被识别为爬虫的概率
    options.add_argument(
        "user-agent=Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    )

    if headless:
        options.add_argument("--headless=new")
        options.add_argument("--no-sandbox")
        options.add_argument("--disable-dev-shm-usage")

    driver = webdriver.Chrome(
        service=Service(ChromeDriverManager().install()),
        options=options
    )

    # 注入 JS，屏蔽 navigator.webdriver 标志
    driver.execute_cdp_cmd(
        "Page.addScriptToEvaluateOnNewDocument",
        {"source": "Object.defineProperty(navigator, 'webdriver', {get: () => undefined})"}
    )

    return driver


# ─────────────────────────────────────────────
# 2. Cookie 管理
# ─────────────────────────────────────────────

COOKIE_PATH = "cookies.pkl"


def save_cookies(driver: webdriver.Chrome, path: str = COOKIE_PATH) -> None:
    """将 Selenium 浏览器的 cookies 完整序列化到本地文件。"""
    with open(path, "wb") as f:
        pickle.dump(driver.get_cookies(), f)
    print(f"✅ Cookies 已保存到 {path}")


def load_cookies_for_selenium(driver: webdriver.Chrome, path: str = COOKIE_PATH) -> bool:
    """
    将本地 cookies 注入 Selenium 浏览器。
    返回 True 表示成功，False 表示文件不存在。
    """
    if not os.path.exists(path):
        print(f"⚠️  Cookie 文件 {path} 不存在，跳过注入。")
        return False

    with open(path, "rb") as f:
        cookies = pickle.load(f)

    if not cookies:
        print(f"⚠️  Cookie 文件 {path} 为空或无效，请重新运行 auth.py 登录。")
        return False

    for cookie in cookies:
        # Selenium 不支持 sameSite=None 以外的部分字段，需过滤
        cookie.pop("sameSite", None)
        try:
            driver.add_cookie(cookie)
        except Exception:
            pass  # 个别字段不合法时静默跳过
    return True


def load_cookies_for_requests(path: str = COOKIE_PATH) -> RequestsCookieJar:
    """
    将本地 cookies 转为 requests.cookies.RequestsCookieJar，
    可直接赋值给 instaloader session：L.context._session.cookies = jar
    """
    jar = RequestsCookieJar()
    if not os.path.exists(path):
        print(f"⚠️  Cookie 文件 {path} 不存在，返回空 jar。")
        return jar

    with open(path, "rb") as f:
        cookies = pickle.load(f)

    if not cookies:
        print(f"⚠️  Cookie 文件 {path} 为空或无效，请重新运行 auth.py 登录。")
        return jar

    for c in cookies:
        jar.set(
            c["name"],
            c["value"],
            domain=c.get("domain", ".instagram.com"),
            path=c.get("path", "/"),
        )
    return jar


# ─────────────────────────────────────────────
# 3. URL 解析
# ─────────────────────────────────────────────

_SHORTCODE_RE = re.compile(r'/(p|reel|tv)/([A-Za-z0-9_-]+)')


def get_shortcode_from_url(url: str) -> str | None:
    """从 Instagram 详情页 URL 中提取 shortcode。"""
    match = _SHORTCODE_RE.search(url)
    return match.group(2) if match else None


# ─────────────────────────────────────────────
# 4. 重试装饰器
# ─────────────────────────────────────────────

def retry(max_times: int = 3, delay: float = 10.0, backoff: float = 1.5):
    """
    通用重试装饰器。
    - max_times : 最大尝试次数（含第一次）
    - delay     : 首次重试前等待秒数
    - backoff   : 每次重试后延时倍增系数
    """
    def decorator(func):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            wait = delay
            for attempt in range(1, max_times + 1):
                try:
                    return func(*args, **kwargs)
                except Exception as e:
                    if attempt < max_times:
                        print(f"  ⚠️  第 {attempt} 次失败，{wait:.0f}s 后重试 [{func.__name__}]: {e}")
                        time.sleep(wait)
                        wait *= backoff
                    else:
                        print(f"  ❌ 已重试 {max_times} 次，放弃 [{func.__name__}]: {e}")
                        raise
        return wrapper
    return decorator


# ─────────────────────────────────────────────
# 5. 人性化延时
# ─────────────────────────────────────────────

def human_sleep(
    base_min: float = 4.0,
    base_max: float = 8.0,
    long_pause_prob: float = 0.1,
    long_min: float = 15.0,
    long_max: float = 30.0,
) -> None:
    """
    模拟真人浏览行为的随机延时。
    - 90% 概率：base_min ~ base_max 秒的正常间隔
    - 10% 概率：long_min ~ long_max 秒的长暂停（模拟查看内容）
    """
    if random.random() < long_pause_prob:
        t = random.uniform(long_min, long_max)
        print(f"  😴 模拟浏览停顿 {t:.1f}s ...")
    else:
        t = random.uniform(base_min, base_max)
    time.sleep(t)
