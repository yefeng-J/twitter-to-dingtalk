"""
Twitter → 钉钉
解析 Twitter 网页嵌入式数据，不依赖任何第三方库
"""
import os
import json
import re
import requests
from datetime import datetime, timedelta, timezone

TWITTER_AUTH_TOKEN = os.environ['TWITTER_AUTH_TOKEN']
TWITTER_USERNAME = os.environ.get('TWITTER_USERNAME', 'binancezh')
DINGTALK_WEBHOOK = os.environ['DINGTALK_WEBHOOK']
KEYWORD = os.environ.get('KEYWORD', '推特')
STATE_FILE = 'last_run.txt'

HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'Accept': 'text/html,application/xhtml+xml',
    'Accept-Language': 'en-US,en;q=0.9',
}


def get_last_run():
    try:
        with open(STATE_FILE, 'r') as f:
            return datetime.fromisoformat(f.read().strip())
    except (FileNotFoundError, ValueError):
        return datetime.now(timezone.utc) - timedelta(hours=2)


def save_last_run(dt):
    with open(STATE_FILE, 'w') as f:
        f.write(dt.isoformat())


def fetch_tweets():
    """从 Twitter 页面提取推文"""
    session = requests.Session()
    session.cookies.set('auth_token', TWITTER_AUTH_TOKEN)

    url = f'https://x.com/{TWITTER_USERNAME}'
    resp = session.get(url, headers=HEADERS, timeout=30)

    if resp.status_code != 200:
        print(f"页面返回 {resp.status_code}")
        return []

    html = resp.text

    # Twitter 页面的嵌入式数据在 __NEXT_DATA__ 或 script 标签中
    # 尝试多种提取方式

    # 方式1: 提取 <script id="__NEXT_DATA__"> 中的 JSON
    m = re.search(r'<script[^>]*id="__NEXT_DATA__"[^>]*>(.*?)</script>', html)
    if m:
        try:
            data = json.loads(m.group(1))
            # 深度查找 tweets
            return extract_from_next_data(data)
        except Exception as e:
            print(f"__NEXT_DATA__ 解析失败: {e}")

    # 方式2: 搜索 window.__INITIAL_STATE__ 
    m = re.search(r'window\.__INITIAL_STATE__\s*=\s*({.*?});', html)
    if m:
        try:
            data = json.loads(m.group(1))
            return extract_from_initial_state(data)
        except Exception as e:
            print(f"__INITIAL_STATE__ 解析失败: {e}")

    # 方式3: 搜索所有 JSON 数据块
    for script in re.findall(r'<script[^>]*type="application/json"[^>]*>(.*?)</script>', html):
        try:
            data = json.loads(script)
            result = extract_from_next_data(data)
            if result:
                return result
        except:
            continue

    print("未能从页面提取推文数据")
    return []


def extract_from_next_data(data):
    """从 __NEXT_DATA__ 结构提取推文"""
    results = []
    
    def deep_search(obj, path=''):
        if isinstance(obj, dict):
            # 查找 tweets/entries 相关字段
            for key in ['entries', 'tweets', 'timeline', 'instructions']:
                if key in obj and isinstance(obj[key], list):
                    for item in obj[key]:
                        tweet = extract_tweet_from_entry(item)
                        if tweet:
                            results.append(tweet)
            for k, v in obj.items():
                deep_search(v, f'{path}.{k}')
        elif isinstance(obj, list):
            for i, item in enumerate(obj):
                tweet = extract_tweet_from_entry(item)
                if tweet:
                    results.append(tweet)
                deep_search(item, f'{path}[{i}]')

    deep_search(data, 'root')
    return results


def extract_tweet_from_entry(entry):
    """从单个 entry 提取推文信息"""
    if not isinstance(entry, dict):
        return None

    # 直接从 entry 查找 tweet 信息
    content = entry.get('content', entry)
    if isinstance(content, dict):
        tweet = content.get('tweet', content.get('item', {}))
    else:
        tweet = entry

    if not isinstance(tweet, dict):
        return None

    result = tweet.get('tweet_results', {}).get('result', tweet.get('results', {}))
    if not isinstance(result, dict):
        return None

    # 提取文本
    legacy = result.get('legacy', result)
    text = legacy.get('full_text', '')
    if not text:
        return None

    # 提取时间
    created_at = legacy.get('created_at', '')
    if not created_at:
        return None

    try:
        created = datetime.strptime(created_at, '%a %b %d %H:%M:%S +0000 %Y')
        created = created.replace(tzinfo=timezone.utc)
    except:
        return None

    tid = result.get('rest_id', legacy.get('id_str', ''))
    return {'text': text, 'time': created, 'id': tid}


def extract_from_initial_state(data):
    """从 __INITIAL_STATE__ 提取推文"""
    results = []
    # 通常 tweets 在 entities/tweets 或 homeTimeline 里
    for key in ['entities', 'tweets', 'homeTimeline']:
        if key in data:
            obj = data[key]
            if isinstance(obj, dict):
                for tid, tweet_data in obj.items():
                    if isinstance(tweet_data, dict):
                        text = tweet_data.get('full_text', '')
                        if text:
                            results.append({
                                'text': text,
                                'time': datetime.now(timezone.utc),
                                'id': tid
                            })
    return results


def main():
    now = datetime.now(timezone.utc)
    print(f"[{now}] 抓取 @{TWITTER_USERNAME}")

    tweets = fetch_tweets()
    print(f"提取到 {len(tweets)} 条推文")

    if not tweets:
        print("尝试备用方案...")
        # 备用：用 syndication API
        synd_url = f'https://syndication.twitter.com/srv/timeline-profile/screen-name/{TWITTER_USERNAME}'
        resp = requests.get(synd_url, headers=HEADERS, timeout=15)
        if resp.status_code == 200:
            body = resp.text
            # 简单的推文文本提取
            pattern = r'"text"\s*:\s*"([^"]+)"'
            texts = re.findall(pattern, body)
            if texts:
                for text in texts[:10]:
                    tweets.append({
                        'text': text.encode().decode('unicode_escape', errors='ignore'),
                        'time': datetime.now(timezone.utc),
                        'id': ''
                    })
                print(f"备用方案提取到 {len(tweets)} 条")
            else:
                print("备用方案也未提取到")
                return

    last_run = get_last_run()
    print(f"上次处理: {last_run.isoformat()}")

    new_tweets = []
    latest_time = last_run

    for tweet in tweets:
        created = tweet['time']
        if created.tzinfo is None:
            created = created.replace(tzinfo=timezone.utc)

        if created > latest_time:
            latest_time = created
        if created > last_run:
            new_tweets.append(tweet)

    if not new_tweets:
        print(f"无新推文（最新: {latest_time.isoformat()}）")
        return

    count = 0
    for tweet in sorted(new_tweets, key=lambda x: x['time']):
        text = tweet['text']
        tid = tweet.get('id', '')
        link = f'https://x.com/{TWITTER_USERNAME}/status/{tid}' if tid else ''
        msg = f"【{KEYWORD}】\n{text}\n{link}" if link else f"【{KEYWORD}】\n{text}"

        print(f"转发 [{tweet['time']}]: {text[:80]}...")

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
    main()
