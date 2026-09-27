"""
Telegram 用户账号 → 钉钉 转发
带钉钉限流保护 + 失败保留进度重试
"""
import os
import time
import asyncio
import requests
from datetime import datetime, timedelta, timezone
from telethon import TelegramClient
from telethon.sessions import StringSession

API_ID = int(os.environ.get('API_ID', '2040'))
API_HASH = os.environ.get('API_HASH', 'b18441a1ff607e10a989891a5462e627')
SESSION_STRING = os.environ['SESSION_STRING']
GROUP_ID = int(os.environ['GROUP_ID'])  # 群 ID，负数
DINGTALK_WEBHOOK = os.environ['DINGTALK_WEBHOOK']
KEYWORD = os.environ.get('KEYWORD', '推特')
STATE_FILE = 'last_run.txt'

# 钉钉限制 20 条/分钟，保守用 3.5 秒间隔（约 17 条/分钟）
SEND_INTERVAL = 3.5
# 单条最多重试次数（针对限流）
MAX_RETRY = 3


def get_last_run():
    try:
        with open(STATE_FILE, 'r') as f:
            return datetime.fromisoformat(f.read().strip())
    except (FileNotFoundError, ValueError):
        return datetime.now(timezone.utc) - timedelta(hours=1)


def save_last_run(dt):
    with open(STATE_FILE, 'w') as f:
        f.write(dt.isoformat())


def send_to_dingtalk(text):
    """发送单条消息到钉钉，自动处理限流重试。返回是否成功"""
    for attempt in range(MAX_RETRY):
        try:
            resp = requests.post(DINGTALK_WEBHOOK, json={
                "msgtype": "text",
                "text": {"content": f"【{KEYWORD}】{text}"}
            }, timeout=10)
            result = resp.json()
            errcode = result.get('errcode')

            if errcode == 0:
                return True
            if errcode == 660026:  # 触发限流
                print(f"    钉钉限流，等待 20 秒后重试 ({attempt + 1}/{MAX_RETRY})")
                time.sleep(20)
                continue

            print(f"    钉钉返回错误: {result}")
            return False
        except Exception as e:
            print(f"    请求异常: {e}")
            time.sleep(5)

    return False


async def main():
    now = datetime.now(timezone.utc)
    print(f"[{now}] 用用户账号监听群 {GROUP_ID}")

    client = TelegramClient(StringSession(SESSION_STRING), API_ID, API_HASH)
    await client.start()

    me = await client.get_me()
    print(f"已登录: {me.first_name}")

    entity = await client.get_entity(GROUP_ID)
    messages = await client.get_messages(entity, limit=50)

    last_run = get_last_run()
    print(f"上次处理: {last_run.isoformat()}")

    new_msgs = []
    for msg in messages:
        if not msg.text:
            continue
        mt = msg.date
        if mt.tzinfo is None:
            mt = mt.replace(tzinfo=timezone.utc)
        if msg.sender_id == me.id:  # 跳过自己发的
            continue
        if mt > last_run:
            new_msgs.append((mt, msg.text))

    if not new_msgs:
        print("无新消息")
        await client.disconnect()
        return

    print(f"发现 {len(new_msgs)} 条新消息，开始逐条转发")

    # 只记录「已成功转发」的进度，失败的不推进，下次可重试
    last_success = last_run
    count = 0

    for mt, text in sorted(new_msgs, key=lambda x: x[0]):
        preview = text.replace('\n', ' ')[:60]
        print(f"转发 [{mt}]: {preview}")

        if send_to_dingtalk(text):
            last_success = mt
            count += 1
            print("    成功")
        else:
            print("    失败，停止本次转发并保留进度，下次重试")
            break

        time.sleep(SEND_INTERVAL)

    save_last_run(last_success)
    await client.disconnect()
    print(f"[{datetime.now()}] 成功发送 {count} 条，进度 → {last_success.isoformat()}")


if __name__ == '__main__':
    asyncio.run(main())
