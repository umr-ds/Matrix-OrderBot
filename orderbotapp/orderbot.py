import asyncio
import logging as log
import os
from os.path import exists

from nio import AsyncClient, RoomMessageText, RoomMemberEvent
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

import order_parser
from orderbotapp.db_classes import setup_db

log.basicConfig(format="%(levelname)s|%(asctime)s:%(message)s", level=log.DEBUG)


class Orderbot:

    def __init__(self):
        self.client = None
        self.session = None
        self.order = None
        self.username = ""
        self.room = ""
        self.msg = []
        self.members = None

    async def connect(self):
        self.username = os.environ["MUSERNAME"]
        if os.environ["MHOMEROOM"]:
            self.room = os.environ["MHOMEROOM"]
        try:
            setup_db()
            db = create_engine("sqlite:///orderbot.db")
            Session = sessionmaker(bind=db)
            self.session = Session()
            self.client = AsyncClient(os.environ['MSERVER'], "@" + self.username)
            log.info(await self.client.login(os.environ['MPASSWORD']))
        except Exception as error:
            log.error(error)

        if exists("next_batch"):
            with open("next_batch", "r") as next_batch_token:
                self.client.next_batch = next_batch_token.read()
        else:
            sync_response = await self.client.sync(3000)
            with open("next_batch", "w") as next_batch_token:
                next_batch_token.write(sync_response.next_batch)

        self.get_members()
        self.client.add_event_callback(self.message_cb, RoomMessageText)
        self.client.add_event_callback(self.join_cb, RoomMemberEvent)
        while True:
            sync_response = await self.client.sync(60000)
            with open("next_batch", "w") as next_batch_token:
                next_batch_token.write(sync_response.next_batch)
            if len(sync_response.rooms.join) == 0 and len(sync_response.rooms.invite) > 0:
                room_id = list(sync_response.rooms.invite.keys())[0]
                await self.client.join(room_id)
                self.room = room_id
                with open("room.env", "w") as room_env:
                    room_env.write(f"MHOMEROOM={room_id}")

            while len(self.msg) > 0:
                content = {
                    "body": f"```{self.msg.pop(0)}```",
                    "msgtype": "m.text"
                }
                await self.client.room_send(self.room, "m.room.message", content)

    async def message_cb(self, room, event):
        if room.room_id != self.room or event.sender == self.username:
            return
        if not event.body.startswith("!orderbot") and not event.body.startswith("!ob"):
            return
        inp = event.body.split()[1:]
        if not inp:
            return
        order, message = order_parser.parse_input(inp, self.session, self.order, event.sender, self.members)
        log.info(f"Body:{event.body}, Msg:{message}")
        self.msg.append(message)
        self.order = order

    async def join_cb(self, room, event):
        if room.room_id == self.room:
            self.get_members()

    def get_members(self):
        self.members = {member.user_id: member.display_name for member in
                        (await self.client.joined_members(self.room)).members}


async def main():
    bot = Orderbot()
    await bot.connect()


if __name__ == '__main__':
    asyncio.run(main())
