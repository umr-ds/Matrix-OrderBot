import asyncio
from pprint import pprint

from nio import AsyncClient, RoomMessageText
from psycopg2 import connect

from config import config


class Bot:

    def __init__(self):
        self.client = None
        self.conn = None

    async def connect(self):
        conf = config('matrix')
        try:
            self.conn = connect(**config('postgresql'))
            self.client = AsyncClient(conf['server'], conf['username'])
            print(await self.client.login(conf['password']))
        except Exception as error:
            print(error)
        finally:
            self.conn.close()

        self.client.add_event_callback(self.message_cb, RoomMessageText)
        await self.client.sync_forever(0)

        async def message_cb(room, event):
            # todo: extract message + name/username + give to parser
            pprint(vars(room))
            pprint(vars(event))


async def main():
    bot = Bot()
    await bot.connect()


if __name__ == '__main__':
    asyncio.run(main())
