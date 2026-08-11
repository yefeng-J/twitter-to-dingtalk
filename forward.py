"""
Twitter RSS → 钉钉 转发脚本
持久化 last_run.txt，RSS.app 更新后不漏任何一条
"""
import os
import time as time_mod
import requests
import feedparser
from datetime import datetime, timedelta, timezone

RSS_FEED_URL = os.environ['RSS_FEED_URL']
DINGTALK_WEBHOOK = os.environ['DINGTALK_WEBHOOK']
KEYWORD = os.environ.get('KEYWORD', '推特')
STATE_FILE = 'last_run.txt'


def get_last_run():
    try:
        with open(STATE_FILE, 'r') as f:
            return datetime.fromisoformat(f.read().strip())
    except (FileNotFoundError, ValueError):
        return datetime.now(timezone.utc) - timedelta(hours=1)


def save_last_run(dt):
    with open(STATE_FILE, 'w') as f:
        f.write(dt.isoformat())


def main():
    now = datetime.now(timezone.utc)
    print(f"[{now}] 检查 RSS")

    feed = feedparser.parse(RSS_FEED_URL)
    if feed.bozo:
        print(f"警告: {feed.bozo_exception}")
    if not feed.entries:
        print("RSS 无条目")
        return

    last_run = get_last_run()
    print(f"上次处理: {last_run.isoformat()}，RSS 共 {len(feed.entries)} 条")

    new_entries = []
    latest_time = last_run

    for entry in feed.entries:
        published = None
        if hasattr(entry, 'published_parsed') and entry.published_parsed:
            published = datetime.fromtimestamp(
                time_mod.mktime(entry.published_parsed), tz=timezone.utc)
        elif hasattr(entry, 'updated_parsed') and entry.updated_parsed:
            published = datetime.fromtimestamp(
                time_mod.mktime(entry.updated_parsed), tz=timezone.utc)
        if published is None:
            continue
        if published > latest_time:
            latest_time = published
        if published > last_run:
            new_entries.append((published, entry))

    if not new_entries:
        print(f"无新条目（最新: {latest_time.isoformat()}）")
        return

    count = 0
    for published, entry in sorted(new_entries, key=lambda x: x[0]):
        title = entry.get('title', '').strip()
        link = entry.get('link', '')
        text = f"{title}\n{link}" if link else title
        print(f"转发 [{published}]: {title[:80]}")

        resp = requests.post(DINGTALK_WEBHOOK, json={
            "msgtype": "text", "text": {"content": f"【{KEYWORD}】{text}"}
        }, timeout=10)
        result = resp.json()
        count += 1
        if result.get("errcode") == 0:
            print("  成功")
        else:
            print(f"  失败: {result}")

    save_last_run(latest_time)
    print(f"[{datetime.now()}] 发送 {count} 条 → {latest_time.isoformat()}")


if __name__ == '__main__':
    main()
