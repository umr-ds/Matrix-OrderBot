import asyncio
import logging as log
import os
import shlex
from os.path import exists

from nio import AsyncClient, RoomMessageText, RoomMemberEvent, SyncError, MatrixRoom, Event
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

import order_parser
from db_classes import setup_db

log.basicConfig(format="%(levelname)s|%(asctime)s: %(message)s", level=log.DEBUG)


class Orderbot:

    def __init__(self):
        self.client = None
        self.session = None
        self.order = None
        self.username = ""
        self.room = ""
        self.msg = []
        self.members = None

    async def connect(self) -> None:
        self.username = os.environ["MUSERNAME"]
        if os.getenv("MHOMEROOM"):
            self.room = os.environ["MHOMEROOM"]
        try:
            setup_db(os.environ["DBPATH"])
            db = create_engine(os.environ["DBPATH"])
            # create session for db
            Session = sessionmaker(bind=db)
            self.session = Session()

            # log into matrix
            self.client = AsyncClient(os.environ['MSERVER'], "@" + self.username)
            log.info(await self.client.login(os.environ['MPASSWORD']))
        except Exception as error:
            log.error(error)

        # load prev. position form next_batch
        if exists("next_batch"):
            with open("next_batch", "r") as next_batch_token:
                self.client.next_batch = next_batch_token.read()
        else:
            # create new next_patch based on the last Event
            sync_response = await self.client.sync()
            with open("next_batch", "w") as next_batch_token:
                next_batch_token.write(sync_response.next_batch)

        # add callback for Messages/Member events
        self.client.add_event_callback(self.message_cb, RoomMessageText)
        self.client.add_event_callback(self.join_cb, RoomMemberEvent)

        # find homeroome
        while True:
            sync_response = await self.client.sync(1000)
            # already in a room, and that room = homerome => end
            if len(sync_response.rooms.join) > 0:
                if os.getenv("MHOMEROOM") and os.getenv("MHOMEROOM") in list(sync_response.rooms.join.keys()):
                    log.info(f"In Room {os.getenv('MHOMEROOM')}")  #
                    self.room = os.getenv('MHOMEROOM')
                    break
                else:
                    os.environ["MHOMEROOM"] = list(sync_response.rooms.join.keys())[0]
                    with open("../room.env", "w") as room_env:
                        room_env.write(f"MHOMEROOM={list(sync_response.rooms.join.keys())[0]}")
                    self.room = os.getenv('MHOMEROOM')
                    log.info(f"joined room {list(sync_response.rooms.join.keys())[0]}")
                    break

            # not in a room => wait for invite
            # if invited:
            if len(sync_response.rooms.join) == 0 and len(sync_response.rooms.invite) > 0:
                room_id = list(sync_response.rooms.invite.keys())[0]
                # join room and save room_id
                await self.client.join(room_id)
                # update next_batch
                with open("next_batch", "w") as next_batch_token:
                    next_batch_token.write(sync_response.next_batch)
                self.room = room_id
                with open("../room.env", "w") as room_env:
                    room_env.write(f"MHOMEROOM={room_id}")
                log.info(f"joined room {room_id}")
                break

    async def listen(self) -> None:
        await self.get_members()
        while True:
            sync_response = await self.client.sync(6000)
            while isinstance(sync_response, SyncError):
                sync_response = await self.client.sync(6000)

            with open("next_batch", "w") as next_batch_token:
                next_batch_token.write(sync_response.next_batch)

            # empty message stack
            while len(self.msg) > 0:
                msg = self.msg.pop(0)
                if "\n" in msg:
                    content = {
                        "body": f"```{msg}```",
                        "format": "org.matrix.custom.html",
                        "formatted_body": f"<pre><code>{msg}</code></pre>",
                        "msgtype": "m.text"
                    }
                else:
                    content = {
                        "body": msg,
                        "msgtype": "m.text"
                    }
                await self.client.room_send(self.room, "m.room.message", content)

    async def message_cb(self, room: MatrixRoom, event: RoomMessageText) -> None:
        # filter out msg from rooms that are not the home room
        if room.room_id != self.room:
            return
        # filter out msg from oneself
        if event.sender == self.username:
            return
        # filter out irrelevant msgs
        if not event.body.startswith("!orderbot") and not event.body.startswith("!ob"):
            return
        inp = shlex.split(event.body)[1:]
        # empty msg
        if not inp:
            return

        if not self.members:
            log.debug("getting members")
            await self.get_members()

        # parse message
        order, response = order_parser.parse_input(inp, self.session, self.order, event.sender, self.members)
        log.debug(f"Body:{event.body}, Msg:{response}")
        # put received response onto msg stack
        self.msg.append(response)
        self.order = order

    # update member list on member event
    async def join_cb(self, room: MatrixRoom, event: RoomMemberEvent) -> None:
        if room.room_id == self.room:
            log.debug("member event occured")
            await self.get_members()

    # get all members from room
    async def get_members(self) -> None:
        self.members = {member.user_id: member.display_name for member in
                        (await self.client.joined_members(self.room)).members}


async def main():
    bot = Orderbot()
    await bot.connect()
    await bot.listen()


if __name__ == '__main__':
    asyncio.run(main())
