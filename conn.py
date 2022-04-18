from nio import AsyncClient, RoomMessageText
import asyncio

import config


async def message_cb(room, event):
    print(room.display_name, room.user_name(event.sender), event.body)


async def main():
    conf = config.config('matrix')
    client = AsyncClient(conf['server'], conf['username'])
    client.add_event_callback(message_cb, RoomMessageText)
    print(await client.login(conf['password']))
    await client.sync_forever(0)


if __name__ == '__main__':
    asyncio.run(main())
