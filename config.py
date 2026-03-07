"""
config.py - 配置文件管理模块
支持从 YAML 配置文件加载设置，提供默认值和验证
"""

import os
from pathlib import Path
from typing import Any

try:
    import yaml
except ImportError:
    yaml = None

CONFIG_FILE = "config.yaml"


class Config:
    """配置管理类，支持从 YAML 文件加载或使用默认值"""

    def __init__(self, config_path: str = CONFIG_FILE):
        self.config_path = config_path
        self._data = self._load_config()

    def _load_config(self) -> dict[str, Any]:
        """加载配置文件，如果不存在则返回默认配置"""
        if not os.path.exists(self.config_path):
            print(f"⚠️  配置文件 {self.config_path} 不存在，使用默认配置")
            return self._default_config()

        if yaml is None:
            print("⚠️  未安装 PyYAML，使用默认配置。安装方法: pip install pyyaml")
            return self._default_config()

        try:
            with open(self.config_path, 'r', encoding='utf-8') as f:
                data = yaml.safe_load(f) or {}
            print(f"✅ 已加载配置文件: {self.config_path}")
            return self._merge_with_defaults(data)
        except Exception as e:
            print(f"⚠️  配置文件加载失败: {e}，使用默认配置")
            return self._default_config()

    def _default_config(self) -> dict[str, Any]:
        """返回默认配置"""
        return {
            'browser': {
                'headless': False,
                'user_agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36',
            },
            'download': {
                'base_dir': 'downloads',
                'save_metadata': False,
                'download_videos': True,
                'download_comments': False,
                'max_retries': 3,
                'retry_delay': 10,
            },
            'behavior': {
                'scroll_pause_min': 2.0,
                'scroll_pause_max': 3.5,
                'human_delay_min': 4.0,
                'human_delay_max': 8.0,
                'long_pause_prob': 0.1,
                'long_pause_min': 15.0,
                'long_pause_max': 30.0,
            },
            'telegram': {
                'enabled': False,
                'bot_token': '',
                'chat_id': '',
                'push_mode': 'batch',  # 'each', 'batch', 'none'
            },
            'cookies': {
                'path': 'cookies.pkl',
            },
        }

    def _merge_with_defaults(self, user_config: dict[str, Any]) -> dict[str, Any]:
        """将用户配置与默认配置合并"""
        defaults = self._default_config()

        for section, values in defaults.items():
            if section not in user_config:
                user_config[section] = values
            elif isinstance(values, dict):
                for key, default_value in values.items():
                    if key not in user_config[section]:
                        user_config[section][key] = default_value

        return user_config

    def get(self, section: str, key: str, default: Any = None) -> Any:
        """获取配置项"""
        return self._data.get(section, {}).get(key, default)

    def get_section(self, section: str) -> dict[str, Any]:
        """获取整个配置段"""
        return self._data.get(section, {})

    @property
    def browser_headless(self) -> bool:
        return self.get('browser', 'headless', False)

    @property
    def browser_user_agent(self) -> str:
        return self.get('browser', 'user_agent', '')

    @property
    def download_base_dir(self) -> str:
        return self.get('download', 'base_dir', 'downloads')

    @property
    def download_videos(self) -> bool:
        return self.get('download', 'download_videos', True)

    @property
    def download_metadata(self) -> bool:
        return self.get('download', 'save_metadata', False)

    @property
    def max_retries(self) -> int:
        return self.get('download', 'max_retries', 3)

    @property
    def retry_delay(self) -> float:
        return self.get('download', 'retry_delay', 10)

    @property
    def telegram_enabled(self) -> bool:
        return self.get('telegram', 'enabled', False)

    @property
    def telegram_token(self) -> str:
        return self.get('telegram', 'bot_token', '')

    @property
    def telegram_chat_id(self) -> str:
        return self.get('telegram', 'chat_id', '')

    @property
    def telegram_push_mode(self) -> str:
        return self.get('telegram', 'push_mode', 'batch')

    @property
    def cookie_path(self) -> str:
        return self.get('cookies', 'path', 'cookies.pkl')

    @property
    def behavior_config(self) -> dict[str, Any]:
        return self.get_section('behavior')


def create_example_config(output_path: str = "config.yaml.example") -> None:
    """创建示例配置文件（带中文注释）"""
    if yaml is None:
        print("⚠️  未安装 PyYAML，无法创建示例配置文件")
        return

    content = """# IG 爬虫配置文件
# 复制此文件为 config.yaml 并根据需要修改

# 浏览器设置
browser:
  # 是否使用无头模式（不显示浏览器窗口）
  # 服务器环境建议设为 true，本地调试建议 false
  headless: false

  # 浏览器 User-Agent，用于伪装成真实浏览器
  # 可以从 https://www.whatismybrowser.com/guides/the-latest-user-agent/ 获取最新的
  user_agent: Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36

# 下载设置
download:
  # 下载文件保存的基础目录
  base_dir: downloads

  # 是否保存帖子元数据（JSON 格式）
  # 包含点赞数、评论数、发布时间等信息
  save_metadata: false

  # 是否下载视频文件
  # 设为 false 则只下载图片
  download_videos: true

  # 是否下载评论
  # 注意：下载评论会显著增加时间
  download_comments: false

  # 下载失败时的最大重试次数
  max_retries: 3

  # 重试前的等待时间（秒）
  # 每次重试会按 1.5 倍递增
  retry_delay: 10

# 行为模拟设置（用于防止被检测为机器人）
behavior:
  # 滚动页面时的暂停时间范围（秒）
  # 程序会在此范围内随机选择一个值
  scroll_pause_min: 2.0
  scroll_pause_max: 3.5

  # 下载每个帖子之间的延时范围（秒）
  # 模拟真人浏览速度
  human_delay_min: 4.0
  human_delay_max: 8.0

  # 长暂停的触发概率（0-1 之间）
  # 0.1 表示 10% 的概率会触发长暂停
  long_pause_prob: 0.1

  # 长暂停的时间范围（秒）
  # 模拟真人停下来仔细查看内容
  long_pause_min: 15.0
  long_pause_max: 30.0

# Telegram 推送设置
telegram:
  # 是否启用 Telegram 推送
  # 设为 true 且填写了 token 和 chat_id 后，会自动推送，不再询问
  enabled: false

  # Telegram Bot Token
  # 从 @BotFather 创建 bot 后获取
  bot_token: ''

  # Telegram Chat ID
  # 从 @userinfobot 获取你的 chat_id
  # 或者使用频道/群组的 chat_id（需要 bot 是管理员）
  chat_id: ''

  # 推送模式
  # each: 每条下载完立即推送（实时）
  # batch: 全部下载完成后统一推送（推荐）
  # none: 不推送
  push_mode: batch

# Cookie 设置
cookies:
  # Cookie 文件路径
  # 首次运行 auth.py 后会自动生成
  path: cookies.pkl
"""

    with open(output_path, 'w', encoding='utf-8') as f:
        f.write(content)

    print(f"✅ 已创建示例配置文件: {output_path}")


if __name__ == "__main__":
    # 测试配置加载
    config = Config()
    print("\n当前配置:")
    print(f"  浏览器无头模式: {config.browser_headless}")
    print(f"  下载目录: {config.download_base_dir}")
    print(f"  Telegram 推送: {config.telegram_enabled}")

    # 创建示例配置
    create_example_config()
