#!/usr/bin/env python3
"""将 cookies.pkl 转换为 cookies.json（供 Rust 监控程序使用）"""
import pickle
import json

def convert_cookies():
    try:
        with open('cookies.pkl', 'rb') as f:
            cookies = pickle.load(f)

        # 转换为 JSON 格式
        cookies_list = []
        for cookie in cookies:
            cookies_list.append({
                'name': cookie['name'],
                'value': cookie['value'],
                'domain': cookie.get('domain', ''),
                'path': cookie.get('path', '/'),
                'secure': cookie.get('secure', False),
                'httpOnly': cookie.get('httpOnly', False),
                'sameSite': cookie.get('sameSite', 'Lax')
            })

        with open('cookies.json', 'w') as f:
            json.dump(cookies_list, f, indent=2)

        print("✅ Cookie 转换成功")
        return True
    except Exception as e:
        print(f"❌ Cookie 转换失败: {e}")
        return False

if __name__ == '__main__':
    convert_cookies()
