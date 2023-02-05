import random
import re
from decimal import Decimal, ROUND_HALF_DOWN
from typing import List

from sqlalchemy import or_, update
from sqlalchemy.orm import Session

from orderbot.db_classes import Participant, Cuts, DB_Order
from orderbot.order import Order

paid_string = "paid amount"


def cent_to_euro(cents: int) -> str:
    """
    convert cent to euro

    :param cents: int
    :return: str
    """
    return "{:.2f}".format(cents / 100)


def euro_to_cent(f: float) -> int:
    """
    convert euro to cent

    :param f: float
    :return: int
    """
    return int(Decimal(f * 100).quantize(Decimal('1'), rounding=ROUND_HALF_DOWN))


def split_tip(tip: int, number_of_shares: int) -> List[int]:
    """
    split tip into shares
    :param tip: int
    :param number_of_shares: int
    :return: List[int]
    """

    l = [tip // number_of_shares] * number_of_shares
    too_much = tip - sum(l)
    if too_much > 0:
        for i in range(too_much):
            l[i] = l[i] + 1
    if too_much < 0:
        for i in range(-too_much):
            l[i] = l[i] - 1
    random.shuffle(l)
    return [x for x in l]


def save_order_in_db(order: Order, session: Session) -> None:
    """
    save order in database

    :param order: Order
    :param session: Session
    :return: None
    """

    # register all user in db, if not already in there.
    all_registered_users = [name for name_tuple in session.query(Participant.name, Participant.matrix_address).all() for
                            name in name_tuple]
    # add order into db
    db_order = order.to_dborder()
    session.add(db_order)
    session.commit()
    tip_shares = split_tip(order.tip, len(order.order))
    # adding all users to participant, cuts
    for index, user in enumerate(order.order):
        if user not in all_registered_users:
            handle = re.match(r"@(\S+):\S+\.\S+", user)
            if handle:
                name = handle.group(1)
                session.add(Participant(name=name, matrix_address=user))
                session.commit()
            else:
                session.add(Participant(name=user))
                session.commit()

        user_id = session.query(Participant.pid) \
            .where(or_(Participant.name == user, Participant.matrix_address == user)) \
            .first()[0]
        user_tip = tip_shares[index]
        for item in order.order[user]:
            session.add(
                Cuts(pid=user_id, oid=db_order.oid, cut=-item[1], name=item[0])
            )
        session.add(
            Cuts(pid=user_id, oid=db_order.oid, cut=-user_tip, name="tip"))
        session.commit()
        # update owned ect.
        session.execute(
            update(Participant).where(Participant.pid == user_id)
            .values(user_total=Participant.user_total - sum(item[1] for item in order.order[user]) - user_tip)
        )
        session.commit()

    for user in order.payers:

        user_id = session.query(Participant.pid) \
            .where(or_(Participant.name == user, Participant.matrix_address == user)) \
            .first()[0]
        session.add(
            Cuts(pid=user_id, oid=db_order.oid, cut=order.payers[user], name=paid_string)
        )
        session.execute(
            update(Participant).where(Participant.pid == user_id)
            .values(user_total=Participant.user_total + order.payers[user])
        )
        session.commit()


def no_active_order() -> (Order, str):
    """
    simple method to streamline reply-message
    """
    return None, "start an order first!"


def set_recommended_payers(order: Order, session: Session) -> None:
    """
    set recommended payers for order based on db balance
    :param order: Order
    :param session: Session
    :return: None
    """
    user = session.query(Participant).where(Participant.is_active.is_(True)).filter(
        Participant.name.in_(order.order.keys())).order_by(Participant.user_total).first()
    if user:
        order.recommended_payer = (user.name.title(), cent_to_euro(user.user_total))


def find_match_in_database(name, session: Session, active: bool = False) -> Participant:
    """
    find a Participant in the database, based on name or matrix_address
    active: if true, only return active users
    :param name: str
    :param session: Session
    :param active: bool
    :return: Participant
    """
    name = name.lower()
    handle = re.match(r"@(\S+):\S+\.\S+", name)
    if handle:
        cur_user = session.query(Participant).where(Participant.matrix_address == name).first()
    else:
        cur_user = session.query(Participant).where(Participant.name == name).first()
    if active:
        if cur_user and cur_user.is_active:
            return cur_user
        else:
            return None
    return cur_user


def get_last_k_orders(session: Session, k: int = 5, delete: bool = False) -> List[Order]:
    """
    get last k orders from db
    if delete is true, delete orders from db
    :param session: Session
    :param k: int
    :param delete: bool
    :return: List[Order]
    """
    orders_oids = session.query(DB_Order.oid, DB_Order.name).order_by(DB_Order.oid.desc()).limit(k).all()
    orders = []
    for (oid, name) in orders_oids:
        cuts = session.query(Cuts, Participant).join(Participant, Cuts.pid == Participant.pid).where(
            Cuts.oid == oid).all()
        ord = Order(name)
        for cut, participant in cuts:
            if cut.name == paid_string:
                pass
            elif cut.name == "tip":
                ord.add_tip(cut.cut)
            else:
                ord.add_pos(participant.name, cut.name, -cut.cut)
        for cut, participant in cuts:
            if cut.name == paid_string:
                ord.pay(participant.name, cut.cut)
        orders.append(ord)
        if delete:
            session.query(Cuts).where(Cuts.oid == oid).delete()
            session.query(DB_Order).where(DB_Order.oid == oid).delete()
            for cut, participant in cuts:
                session.execute(
                    update(Participant).where(Participant.pid == participant.pid)
                    .values(user_total=Participant.user_total - cut.cut)
                )
            session.commit()
    return orders
