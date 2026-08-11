"""
Twitter → 钉钉 直连方案
用 twikit 库 + auth_token 直接读取推文
"""
import os
import json
import asyncio
import requests
from datetime import datetime, timedelta, timezone

TWITTER_AUTH_TOKEN = os.environ['TWITTER_AUTH_TOKEN']
TWITTER_USERNAME = os.environ.get('TWITTER_USERNAME', 'binancezh')
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


async def main():
    from twikit import Client

    now = datetime.now(timezone.utc)
    print(f"[{now}] 开始抓取 @{TWITTER_USERNAME}")

    client = Client('en-US')
    client.set_cookies({'auth_token': TWITTER_AUTH_TOKEN})

    # 获取用户
    try:
        user = await client.get_user_by_screen_name(TWITTER_USERNAME)
    except Exception as e:
        print(f"获取用户失败: {e}")
        return

    print(f"用户 ID: {user.id}, 粉丝: {user.followers_count}")

    # 获取最新推文
    try:
        tweets = await user.get_tweets('Tweets', count=20)
    except Exception as e:
        print(f"获取推文失败: {e}")
        return

    last_run = get_last_run()
    print(f"上次处理: {last_run.isoformat()}，获取到 {len(tweets)} 条推文")

    new_tweets = []
    latest_time = last_run

    for tweet in tweets:
        created = tweet.created_at
        if created.tzinfo is None:
            created = created.replace(tzinfo=timezone.utc)

        if created > latest_time:
            latest_time = created
        if created > last_run:
            text = tweet.text or ''
            tid = tweet.id or ''
            link = f'https://x.com/{TWITTER_USERNAME}/status/{tid}'
            new_tweets.append((created, text, link))

    if not new_tweets:
        print(f"没有新推文（最新: {latest_time.isoformat()}）")
        return

    count = 0
    for created, text, link in sorted(new_tweets, key=lambda x: x[0]):
        msg = f"【{KEYWORD}】\n{text}\n{link}"
        print(f"转发 [{created}]: {text[:80]}...")

        resp = requests.post(DINGTALK_WEBHOOK, json={
            "msgtype": "text",
            "text": {"content": msg}
        }, timeout=10)
        result = resp.json()
        count += 1
        print(f"  {'成功' if result.get('errcode') == 0 else '失败: ' + str(result)}")

    save_last_run(latest_time)
    print(f"[{datetime.now()}] 发送 {count} 条，记录 → {latest_time.isoformat()}")


if __name__ == '__main__':
    asyncio.run(main())
