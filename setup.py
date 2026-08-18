"""
本地运行一次，生成 SESSION_STRING
凭证已内置，只需输入手机号和验证码
"""
import asyncio
from telethon import TelegramClient
from telethon.sessions import StringSession

# Telegram Desktop 公开凭证
API_ID = 2040
API_HASH = "b18441a1ff607e10a989891a5462e627"


async def main():
    print("=" * 55)
    print("  Telegram 用户账号登录")
    print("=" * 55)

    client = TelegramClient(StringSession(), API_ID, API_HASH)
    await client.start()

    me = await client.get_me()
    print(f"\n✅ 登录成功: {me.first_name} (@{me.username})")

    session_string = client.session.save()

    # 保存到文件，方便复制
    with open('session_string.txt', 'w', encoding='utf-8') as f:
        f.write(session_string)

    print("\n" + "=" * 55)
    print("  SESSION_STRING 已保存到 session_string.txt")
    print("=" * 55)
    print(session_string)
    print("=" * 55)
    print("\n⚠️ 复制上面这串，存为 GitHub Secret，不要泄露")


if __name__ == '__main__':
    asyncio.run(main())
