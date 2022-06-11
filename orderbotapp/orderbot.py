import asyncio
import datetime
import os
from os.path import exists

from nio import AsyncClient, RoomMessageText
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

import order_parser
from orderbotapp.db_classes import setup_db


class Orderbot:

    def __init__(self):
        self.client = None
        self.conn = None
        self.cursor = None
        self.order = None
        self.username = ""
        self.room = ""
        self.msg = []

    async def connect(self):
        self.username = os.environ["MUSERNAME"]
        self.room = os.environ["MHOMEROOM"]
        try:
            setup_db()
            db = create_engine("sqlite:///orderbot.db")
            Session = sessionmaker(bind=db)
            session = Session()
            self.client = AsyncClient(os.environ['MSERVER'], "@" + self.username)
            print(datetime.datetime.now(), await self.client.login(os.environ['MPASSWORD']))
            if exists("next_batch"):
                with open("next_batch", "r") as next_batch_token:
                    self.client.next_batch = next_batch_token.read()
            else:
                sync_response = await self.client.sync(3000)
                with open("next_batch", "w") as next_batch_token:
                    next_batch_token.write(sync_response.next_batch)
        except Exception as error:
            print(error)

        self.client.add_event_callback(self.message_cb, RoomMessageText)
        while True:
            sync_response = await self.client.sync(60000)
            with open("next_batch", "w") as next_batch_token:
                next_batch_token.write(sync_response.next_batch)
            while len(self.msg) > 0:
                content = {
                    "body": self.msg.pop(0),
                    "msgtype": "m.text"

                }
                await self.client.room_send(self.room, "m.room.message", content)

    async def message_cb(self, room, event):
        if event.sender == self.username:
            return
        if not event.body.startswith("!orderbot") and not event.body.startswith("!ob"):
            return
        inp = event.body.split()[1:]
        if not inp:
            return 
        order, message = order_parser.parse_input(inp, self.conn, self.cursor, self.order, event.sender)
        #logging
        print(datetime.datetime.now(), event.body, message)
        self.msg.append(message)
        self.order = order


async def main():
    bot = Orderbot()
    await bot.connect()


if __name__ == '__main__':
    asyncio.run(main())
