"""
Telegram 用户账号 → 钉钉 转发
用 Telethon 以用户身份监听群消息，突破 Bot 互不可见限制
"""
import os
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
    now = datetime.now(timezone.utc)
    print(f"[{now}] 用用户账号监听群 {GROUP_ID}")

    client = TelegramClient(StringSession(SESSION_STRING), API_ID, API_HASH)
    await client.start()

    me = await client.get_me()
    print(f"已登录: {me.first_name} (@{me.username})")

    entity = await client.get_entity(GROUP_ID)

    # 获取最近消息
    messages = await client.get_messages(entity, limit=30)

    last_run = get_last_run()
    print(f"上次处理: {last_run.isoformat()}")

    new_msgs = []
    latest_time = last_run

    for msg in messages:
        if not msg.text:
            continue
        mt = msg.date
        if mt.tzinfo is None:
            mt = mt.replace(tzinfo=timezone.utc)
        # 跳过自己发的消息
        if msg.sender_id == me.id:
            continue
        if mt > latest_time:
            latest_time = mt
        if mt > last_run:
            new_msgs.append((mt, msg.text, msg.sender_id))

    if not new_msgs:
        print(f"无新消息（最新: {latest_time.isoformat()}）")
        await client.disconnect()
        return

    count = 0
    for mt, text, sender_id in sorted(new_msgs, key=lambda x: x[0]):
        print(f"转发 [{mt}]: {text[:80]}")

        resp = requests.post(DINGTALK_WEBHOOK, json={
            "msgtype": "text",
            "text": {"content": f"【{KEYWORD}】{text}"}
        }, timeout=10)
        result = resp.json()
        count += 1
        print(f"  {'成功' if result.get('errcode') == 0 else '失败:' + str(result)}")

    save_last_run(latest_time)
    await client.disconnect()
    print(f"[{datetime.now()}] 发送 {count} 条 → {latest_time.isoformat()}")


if __name__ == '__main__':
    asyncio.run(main())
