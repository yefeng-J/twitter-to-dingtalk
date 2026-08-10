"""
Twitter RSS → 钉钉 转发脚本
用于 GitHub Actions 定时运行，每 15 分钟检查 RSS 更新
"""
import os
import sys
import requests
import feedparser
from datetime import datetime, timedelta, timezone

RSS_FEED_URL = os.environ['RSS_FEED_URL']
DINGTALK_WEBHOOK = os.environ['DINGTALK_WEBHOOK']
KEYWORD = os.environ.get('KEYWORD', '推特')


def main():
    print(f"[{datetime.now()}] 开始检查 RSS: {RSS_FEED_URL}")

    feed = feedparser.parse(RSS_FEED_URL)

    if feed.bozo:
        print(f"RSS 解析警告: {feed.bozo_exception}")

    if not feed.entries:
        print("RSS 中没有条目")
        return

    now = datetime.now(timezone.utc)
    cutoff = now - timedelta(minutes=30)
    count = 0

    for entry in feed.entries:
        # 解析发布时间
        published = None
        if hasattr(entry, 'published_parsed') and entry.published_parsed:
            import time
            published = datetime.fromtimestamp(time.mktime(entry.published_parsed), tz=timezone.utc)
        elif hasattr(entry, 'updated_parsed') and entry.updated_parsed:
            import time
            published = datetime.fromtimestamp(time.mktime(entry.updated_parsed), tz=timezone.utc)

        if published is None or published <= cutoff:
            continue

        title = entry.get('title', '无标题').strip()
        link = entry.get('link', '')

        text = title
        if link:
            text += f"\n{link}"

        print(f"新推文: {title}")

        payload = {
            "msgtype": "text",
            "text": {"content": f"【{KEYWORD}】{text}"}
        }
        resp = requests.post(DINGTALK_WEBHOOK, json=payload, timeout=10)
        result = resp.json()
        count += 1

        if result.get("errcode") == 0:
            print(f"  钉钉发送成功")
        else:
            print(f"  钉钉发送失败: {result}")

    print(f"[{datetime.now()}] 完成，发送了 {count} 条")


if __name__ == '__main__':
    main()
