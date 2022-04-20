import asyncio
from pprint import pprint

from nio import AsyncClient, RoomMessageText
from psycopg2 import connect

import order_parser
import setup
from config import config


class Bot:

    def __init__(self):
        self.client = None
        self.conn = None
        self.cursor = None
        self.order = None
        self.username = ""
        self.room = ""
        self.msg = []

    async def connect(self):
        conf = config('matrix')
        self.username = conf["username"]
        self.room = conf["homeroom"]
        try:
            self.conn = connect(**config('postgresql'))
            self.cursor = self.conn.cursor()
            self.client = AsyncClient(conf['server'], conf['username'])
            print(await self.client.login(conf['password']))
            setup.setup(self.conn, self.cursor)
        except Exception as error:
            print(error)
        #finally:
            #self.cursor.close()
            #self.conn.close()

        self.client.add_event_callback(self.message_cb, RoomMessageText)
        while(True):
            sync_response = await self.client.sync(3000)
            print(self.msg, self.room, len(self.msg))
            while len(self.msg) > 0:
                content = {
                    "body": self.msg.pop(0),
                    "msgtype": "m.text"

                }
                await self.client.room_send(self.room, "m.room.message", content)


    async def message_cb(self, room, event):
        print(event.body)
        if event.sender == self.username:
            print("own message, ignored")
        inp = event.body.lower().split()
        result, order, message = order_parser.parse_input(inp, self.conn, self.cursor, self.order)
        print(result,order,message)
        if message == "No order active atm, user Start" or message == "empty string":
            return
        self.msg.append(message)
        if result:
            self.order = order
        if self.order is not None:
            pprint(vars(self.order))


async def main():
    bot = Bot()
    await bot.connect()


if __name__ == '__main__':
    asyncio.run(main())
