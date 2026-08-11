"""
Twitter RSS → 钉钉 转发脚本
使用 last_run.txt 持久化记录最后处理时间，不漏任何一条
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
            ts = f.read().strip()
            return datetime.fromisoformat(ts)
    except (FileNotFoundError, ValueError):
        # 首次运行：以「1小时前」为起点，历史推文不会涌入
        return datetime.now(timezone.utc) - timedelta(hours=1)


def save_last_run(dt):
    with open(STATE_FILE, 'w') as f:
        f.write(dt.isoformat())


def main():
    now = datetime.now(timezone.utc)
    print(f"[{now}] 开始检查 RSS")

    feed = feedparser.parse(RSS_FEED_URL)
    if feed.bozo:
        print(f"RSS 解析警告: {feed.bozo_exception}")
    if not feed.entries:
        print("RSS 中没有条目")
        return

    last_run = get_last_run()
    print(f"上次处理时间: {last_run.isoformat()}")

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
        print(f"没有新条目（RSS 最新条目时间: {latest_time.isoformat()}）")
        return

    count = 0
    for published, entry in sorted(new_entries, key=lambda x: x[0]):
        title = entry.get('title', '无标题').strip()
        link = entry.get('link', '')
        text = f"{title}\n{link}" if link else title

        print(f"转发 [{published}]: {title[:80]}")

        payload = {
            "msgtype": "text",
            "text": {"content": f"【{KEYWORD}】{text}"}
        }
        resp = requests.post(DINGTALK_WEBHOOK, json=payload, timeout=10)
        result = resp.json()
        count += 1
        if result.get("errcode") == 0:
            print("  成功")
        else:
            print(f"  失败: {result}")

    save_last_run(latest_time)
    print(f"[{datetime.now()}] 完成，发送 {count} 条，记录时间 → {latest_time.isoformat()}")


if __name__ == '__main__':
    main()
