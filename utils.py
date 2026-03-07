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

try:
    from config import Config
    _config = Config()
except ImportError:
    _config = None


# ─────────────────────────────────────────────
# 1. 浏览器初始化
# ─────────────────────────────────────────────

def init_driver(headless: bool = None) -> webdriver.Chrome:
    """
    初始化带防检测参数的 Chrome 浏览器。
    headless=True 时以无头模式运行（适合服务器环境）。
    如果未指定，则从配置文件读取。
    """
    if headless is None and _config:
        headless = _config.browser_headless
    elif headless is None:
        headless = False

    options = webdriver.ChromeOptions()
    options.add_argument("--disable-blink-features=AutomationControlled")
    options.add_experimental_option("excludeSwitches", ["enable-automation"])
    options.add_experimental_option("useAutomationExtension", False)

    # 伪装 User-Agent，降低被识别为爬虫的概率
    user_agent = _config.browser_user_agent if _config else (
        "user-agent=Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    )
    options.add_argument(f"user-agent={user_agent}" if not user_agent.startswith("user-agent=") else user_agent)

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

COOKIE_PATH = _config.cookie_path if _config else "cookies.pkl"


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

def retry(max_times: int = None, delay: float = None, backoff: float = 1.5):
    """
    通用重试装饰器。
    - max_times : 最大尝试次数（含第一次），如果为 None 则从配置读取
    - delay     : 首次重试前等待秒数，如果为 None 则从配置读取
    - backoff   : 每次重试后延时倍增系数
    """
    if max_times is None and _config:
        max_times = _config.max_retries
    elif max_times is None:
        max_times = 3

    if delay is None and _config:
        delay = _config.retry_delay
    elif delay is None:
        delay = 10.0

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
    base_min: float = None,
    base_max: float = None,
    long_pause_prob: float = None,
    long_min: float = None,
    long_max: float = None,
) -> None:
    """
    模拟真人浏览行为的随机延时。
    - 90% 概率：base_min ~ base_max 秒的正常间隔
    - 10% 概率：long_min ~ long_max 秒的长暂停（模拟查看内容）
    如果未指定参数，则从配置文件读取。
    """
    if _config:
        behavior = _config.behavior_config
        base_min = base_min if base_min is not None else behavior.get('human_delay_min', 4.0)
        base_max = base_max if base_max is not None else behavior.get('human_delay_max', 8.0)
        long_pause_prob = long_pause_prob if long_pause_prob is not None else behavior.get('long_pause_prob', 0.1)
        long_min = long_min if long_min is not None else behavior.get('long_pause_min', 15.0)
        long_max = long_max if long_max is not None else behavior.get('long_pause_max', 30.0)
    else:
        base_min = base_min if base_min is not None else 4.0
        base_max = base_max if base_max is not None else 8.0
        long_pause_prob = long_pause_prob if long_pause_prob is not None else 0.1
        long_min = long_min if long_min is not None else 15.0
        long_max = long_max if long_max is not None else 30.0

    if random.random() < long_pause_prob:
        t = random.uniform(long_min, long_max)
        print(f"  😴 模拟浏览停顿 {t:.1f}s ...")
    else:
        t = random.uniform(base_min, base_max)
    time.sleep(t)
