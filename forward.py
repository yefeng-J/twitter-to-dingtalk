"""
Twitter → 钉钉 直连方案
用 auth_token 直接请求 Twitter 接口，不需要 RSS 中转
"""
import os
import json
import re
import time as time_mod
import requests
from datetime import datetime, timedelta, timezone
from urllib.parse import quote

TWITTER_AUTH_TOKEN = os.environ['TWITTER_AUTH_TOKEN']
TWITTER_USERNAME = os.environ.get('TWITTER_USERNAME', 'binancezh')
DINGTALK_WEBHOOK = os.environ['DINGTALK_WEBHOOK']
KEYWORD = os.environ.get('KEYWORD', '推特')
STATE_FILE = 'last_run.txt'

# 通用 Twitter API 配置（无需 key）
GUEST_TOKEN_URL = 'https://api.twitter.com/1.1/guest/activate.json'
HEADERS = {
    'authorization': 'Bearer AAAAAAAAAAAAAAAAAAAAANRILgAAAAAAnNwIzUejRCOuH5E6I8xnZz4puTs=1Zv7ttfk8LF81IUq16cHjhLTvJu4FA33AGWWjCpTnA',
    'user-agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
}


def get_guest_token(session):
    """获取 guest token（无需登录）"""
    resp = session.post(GUEST_TOKEN_URL, headers=HEADERS)
    return resp.json().get('guest_token', '')


def get_user_id(session, username, guest_token):
    """通过用户名获取用户 ID"""
    headers = {**HEADERS, 'x-guest-token': guest_token}
    url = f'https://api.twitter.com/1.1/users/show.json?screen_name={username}'
    resp = session.get(url, headers=headers)
    data = resp.json()
    return str(data.get('id_str', ''))


def search_tweets(session, username, guest_token, count=20):
    """获取用户最新推文（使用 search API 变通）"""
    headers = {
        **HEADERS,
        'x-guest-token': guest_token,
        'cookie': f'auth_token={TWITTER_AUTH_TOKEN}; ct0=',
    }
    # 用 from: 语法搜这个用户最近推文
    query = quote(f'from:{username}')
    url = f'https://api.twitter.com/1.1/search/tweets.json?q={query}&count={count}&tweet_mode=extended&result_type=recent'
    resp = session.get(url, headers=headers)
    if resp.status_code != 200:
        print(f"API 返回 {resp.status_code}: {resp.text[:200]}")
        return []
    return resp.json().get('statuses', [])


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
    print(f"[{now}] 开始抓取 @{TWITTER_USERNAME}")

    session = requests.Session()
    guest_token = get_guest_token(session)
    if not guest_token:
        print("获取 guest_token 失败")
        return
    print(f"guest_token: {guest_token[:20]}...")

    tweets = search_tweets(session, TWITTER_USERNAME, guest_token)
    if not tweets:
        print("API v1.1 不可用，尝试备用接口...")
        # 备用：尝试 REST API
        user_id = get_user_id(session, TWITTER_USERNAME, guest_token)
        if not user_id:
            print("无法获取用户 ID，退出")
            return
        print(f"用户 ID: {user_id}")
        # 尝试 REST timeline
        headers = {
            **HEADERS,
            'x-guest-token': guest_token,
            'cookie': f'auth_token={TWITTER_AUTH_TOKEN}',
        }
        url = f'https://api.twitter.com/1.1/statuses/user_timeline.json?screen_name={TWITTER_USERNAME}&count=20&tweet_mode=extended&include_rts=false'
        resp = session.get(url, headers=headers)
        if resp.status_code == 200:
            tweets = resp.json()
        else:
            print(f"备用接口也失败: {resp.status_code} {resp.text[:200]}")
            return

    last_run = get_last_run()
    print(f"上次处理: {last_run.isoformat()}，获取到 {len(tweets)} 条推文")

    new_tweets = []
    latest_time = last_run

    for tweet in tweets:
        created = datetime.strptime(tweet['created_at'], '%a %b %d %H:%M:%S +0000 %Y')
        created = created.replace(tzinfo=timezone.utc)

        if created > latest_time:
            latest_time = created
        if created > last_run:
            text = tweet.get('full_text', tweet.get('text', ''))
            tid = tweet.get('id_str', '')
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
        print(f"  {'成功' if result.get('errcode')==0 else '失败: '+str(result)}")

    save_last_run(latest_time)
    print(f"[{datetime.now()}] 发送 {count} 条，记录 → {latest_time.isoformat()}")


if __name__ == '__main__':
    main()
