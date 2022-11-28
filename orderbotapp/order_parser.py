import argparse
import logging
import random
import re
from decimal import Decimal, ROUND_HALF_DOWN

from sqlalchemy import or_, update, and_
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from db_classes import Participant, Cuts, DB_Order
from order import Order
from typing import List, Dict, Any

cmd = [
    "register",
    "add",  # add pos to order
    "remove",  # add all pos from given user
    "tip",  # add tip
    "start",  # start new order
    "cancel",  # cancel order
    "end",  # end order and distribute cut
    "print",
    "payout",
    "add",
    "balance",
    "join",
    "all",
    "reopen",
    "suggest",
    "init",
    "deinit",
]


def cent_to_euro(cents: int) -> str:
    return "{:.2f}".format(cents / 100)


def euro_to_cent(f: float) -> int:
    return int(Decimal(f * 100).quantize(Decimal('1'), rounding=ROUND_HALF_DOWN))


def split_tip(tip: int, number_of_shares: int) -> List[int]:
    """
    Precisely splits the tip.
    :param tip: the tip
    :param number_of_shares: The number of shares
    :return: A list of Decimals, summing to the tip.
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
                Cuts(pid=user_id, oid=db_order.oid, cut=item[1], name=item[0])
            )
        session.add(
            Cuts(pid=user_id, oid=db_order.oid, cut=user_tip, name="tip"))
        session.commit()

        # update owned ect.
        session.execute(
            update(Participant).where(Participant.pid == user_id)
            .values(user_total=Participant.user_total - sum(item[1] for item in order.order[user]) - user_tip)
        )
        session.commit()


def no_active_order() -> (Order, str):
    """
    simple method to streamline reply-message
    """
    return None, "start an order first!"


def check_name_in_db(name: str, session: Session) -> Participant:
    return session.query(Participant).where(Participant.name == name.lower()).first()


def check_address_in_db(address: str, session: Session) -> Participant:
    return session.query(Participant).where(Participant.matrix_address == address.lower()).first()


def update_part(pid: int, cut: int, session: Session) -> None:
    session.execute(
        update(Participant).where(Participant.pid == pid)
        .values(user_total=Participant.user_total + cut)
    )
    session.commit()


def set_recommended_payers(order: Order, session: Session) -> None:
    user = session.query(Participant).where(Participant.is_active.is_(True)).filter(Participant.name.in_(order.order.keys())).order_by(Participant.user_total).first()
    if user:
        order.recommended_payer = (user.name.title(), cent_to_euro(user.user_total))


def find_match_in_database(name, session: Session) -> Participant:
    handle = re.match(r"@(\S+):\S+\.\S+", name)
    if handle:
        cur_user = session.query(Participant).where(Participant.matrix_address == name).first()
    else:
        cur_user = session.query(Participant).where(Participant.name == name).first()
    return cur_user


def parse_input(inp: List[str], session: Session, order: Order, sender: str, members: List[str]) -> (Order, str):
    def add(namespace: Dict[str, Any]) -> (Order, str):
        order_to_return = order
        msg = ""
        price = euro_to_cent(namespace['price'])
        if namespace["name"] is None:
            p = check_address_in_db(sender, session)
            if not p:
                return order, "Register user first with !ob join"
            name = p.name
        else:
            p = check_name_in_db(namespace["name"], session)
            if not p:
                return order, "Register user first with !ob register <name>"
            name = p.name
        if order_to_return is None:
            order_to_return, msg = start({"name": ["an", "unnamed", "order"]})
            msg = msg + "\n"
        meal_name = " ".join(namespace["order name"])
        order_to_return.add_pos(user=name, item=meal_name, amount=price)
        return order_to_return, msg + f"Order added for {name.title()}, order: {meal_name}, price: {cent_to_euro(price)}"

    def start(namespace: Dict[str, Any]) -> (Order, str):
        if order is None:
            if namespace["name"] is None or namespace["name"] == []:
                return Order(), "Started new collective order"
            else:
                return Order(" ".join(namespace["name"])), "Started new collective order with Name: " + " ".join(
                    namespace["name"])
        else:
            return order, "Finish current collective order first"

    def cancel(*_) -> (Order, str):
        return None, "Cancelled current collective order"

    def print_order(namespace: Dict[str, Any]) -> (Order, str):
        if order is None:
            return no_active_order()

        set_recommended_payers(order, session)
        if namespace["self"]:
            name = members[sender].lower()
            if name in order.order:
                return order, order.print_order(name)
            else:
                return order, f"{name.title()} not in current order"
        else:
            return order, order.print_order()

    def tip(namespace: Dict[str, Any]) -> (Order, str):
        if order is None:
            return no_active_order()
        ttip = euro_to_cent(namespace['tip'])
        if ttip > 0:
            order.add_tip(ttip)
            return order, f"Added tip: {cent_to_euro(ttip)}"
        else:
            return order, f"negative tip"

    def remove(namespace: Dict[str, Any]) -> (Order, str):
        if order is None:
            return no_active_order()
        remove_all = namespace["all"]
        order_to_remove = namespace["order"]
        if namespace["name"] is None:
            name = members[sender].lower()
        else:
            name = namespace["name"].lower()

        if remove_all or order_to_remove is None:
            order.remove(name)
            return order, f"Removed user {name.title()} from order"
        else:
            order.remove(name, order_to_remove)
            return order, f"Removed order {namespace['order']} for {name.title()} from order"

    def pay(namespace: Dict[str, Any]) -> (Order, str):
        if order is None:
            return no_active_order()
        if namespace["name"] is None:
            p = check_address_in_db(sender, session)
            if not p:
                return order, "Register user first with !ob join"
            name = p.name
        else:
            p = check_name_in_db(" ".join(namespace["name"]), session)
            if not p:
                return order, "Register user first with !ob register <name>"
            name = p.name
        if namespace["amount"] is None:
            order.pay(name)
            save_order_in_db(order, session)
            return None, "order paid\n" + str(order)
        elif euro_to_cent(namespace["amount"]) >= order.price + order.tip:
            order.add_tip(euro_to_cent(namespace["amount"]) - (order.price + order.tip))
            order.pay(name)
            save_order_in_db(order, session)
            return None, "order paid\n" + str(order)
        else:
            return order, f"amount must be greater than {cent_to_euro(order.price + order.tip)}"

    def payout(namespace: Dict[str, Any]) -> (Order, str):
        if namespace["name"] is None:
            cur_user = check_address_in_db(sender, session)
            if not cur_user:
                return order, "User not registered"
        else:
            name = " ".join(namespace["name"]).lower()
            cur_user = check_name_in_db(name, session)
            if not cur_user:
                return order, "User not registered"
        debt = cur_user.user_total
        name = cur_user.name
        if debt != 0:
            if debt > 0:
                all_user = session.query(Participant).where(Participant.user_total < 0).order_by(
                    Participant.user_total.asc()).all()
                if not all_user:
                    return order, "all debtors"
                all_user_subset = []
                subset_debt = 0
                while subset_debt < debt and all_user:
                    cur = all_user.pop()
                    all_user_subset.append(cur)
                    subset_debt = subset_debt - cur.user_total
                diffs = []
                for user in all_user_subset:
                    user_bal = user.user_total
                    change = min(user_bal + debt, 0)
                    diffs.append((user.name, user_bal - change))
                    session.execute(
                        update(Participant).where(Participant.pid == user.pid)
                        .values(user_total=change)
                    )
                    debt = max(debt + user_bal, 0)
                session.commit()
                if debt > 0:
                    session.execute(
                        update(Participant).where(Participant.pid == all_user_subset[0].pid)
                        .values(user_total=debt)
                    )
                    tup = diffs[0]
                    diffs[0] = (tup[0], tup[1] - debt)
                session.execute(
                    update(Participant).where(Participant.pid == cur_user.pid)
                    .values(user_total=0)
                )
                session.commit()
                return order, f"{name.title()} receives from <=\n" + "\n".join(
                    f"{item[0].title()} : {cent_to_euro(- item[1])}" for item in diffs)

            elif debt < 0:
                all_user = session.query(Participant).where(Participant.user_total > 0).order_by(
                    Participant.user_total.desc()).all()
                if not all_user:
                    return order, "all in debt"
                all_user_subset = []
                subset_debt = 0
                while subset_debt > debt and all_user:
                    cur = all_user.pop()
                    all_user_subset.append(cur)
                    subset_debt = subset_debt - cur.user_total
                diffs = []
                for user in all_user_subset:
                    user_bal = user.user_total
                    change = max(user_bal + debt, 0)
                    diffs.append((user.name, user_bal - change))
                    debt = min(debt + user_bal, 0)
                    session.execute(
                        update(Participant).where(Participant.pid == user.pid)
                        .values(user_total=change)
                    )
                session.commit()
                if debt < 0:
                    session.execute(
                        update(Participant).where(Participant.pid == all_user_subset[0].pid)
                        .values(user_total=debt)
                    )
                    tup = diffs[0]
                    diffs[0] = (tup[0], tup[1] - debt)
                session.execute(
                    update(Participant).where(Participant.pid == cur_user.pid)
                    .values(user_total=0)
                )
                session.commit()
                return order, f"{name.title()} pay => \n" + "\n".join(
                    f"{item[0].title()} : {cent_to_euro(item[1])}" for item in diffs)
        else:
            return order, "Nothing to payout"

    def add_money(namespace: Dict[str, Any]) -> (Order, str):
        name = " ".join(namespace["name"]).lower()
        cur_user = find_match_in_database(name, session)
        if cur_user is None:
            return order, f"User {name.title()} not registered"
        bal = euro_to_cent(namespace["balance"])
        session.add(
            Cuts(pid=cur_user.pid, cut=bal, name="manual")
        )
        session.commit()
        cur_user.user_total = cur_user.user_total + bal
        session.commit()
        return order, f"Added {cent_to_euro(bal)} to {cur_user.name.title()}'s balance"

    def balance(*_) -> (Order, str):
        all_balance = session.query(Participant.name, Participant.matrix_address, Participant.user_total).where(Participant.is_active.is_(True)).order_by(
            Participant.user_total.desc()).all()
        if not all_balance:
            return order, "no participants (yet)"
        max_name = max(len(user.name) for user in all_balance)
        max_address = max([len(user.matrix_address) for user in all_balance if user.matrix_address] + [len("None")])
        max_balance = max(len(str(user.user_total)) for user in all_balance) + 1
        msg = "Current balances: \n"
        msg = msg + "\n".join(
            [
                f"{user.name.title():<{max_name}} ({user.matrix_address if user.matrix_address else 'None':>{max_address}}): {cent_to_euro(user.user_total):>{max_balance}}"
                for user in all_balance])
        return order, msg

    def join(namespace: Dict[str, Any]) -> (Order, str):
        if namespace["all"]:
            users = [user.matrix_address for user in session.query(Participant).all()]
            user_names = [user.name for user in session.query(Participant).all()]
            added_users = []
            for user in members:
                if user not in users and members[user].lower() not in user_names and "orderbot" not in user.lower():
                    # case 1: user name not yet taken, user matrix address not yet taken
                    session.add(Participant(matrix_address=user.lower(), name=members[user].lower()))
                    added_users.append(user)
                elif user not in users and "orderbot" not in user.lower() and members[user].lower() in user_names:
                    # case 2: username already taken
                    taken_username = session.query(Participant).where(Participant.name == members[user].lower()).first()
                    # case 2.1: user has not set a matrix address yet
                    if taken_username.matrix_address is None:
                        session.execute(
                            update(Participant).where(Participant.name == members[user].lower())
                            .values(matrix_address=user.lower())
                        )
                        added_users.append(user)
                    else:
                        # case 2.2: user has already registered with a different matrix address
                        session.add(Participant(matrix_address=user.lower(), name=members[user].lower() + user.lower()))
            session.commit()
            if not added_users:
                ret = "No new users added"
            else:
                ret = "\n".join([f"added {user}:{members[user].title()}" for user in added_users])
            return order, ret
        else:
            user = session.query(Participant).where(Participant.matrix_address == sender.lower()).all()
            username = session.query(Participant).where(Participant.name == members[sender].lower()).all()
            if user:
                return order, "User already registered"
            else:
                session.add(Participant(matrix_address=sender.lower(), name=members[sender].lower()))
                session.commit()
                return order, f"Added {members[sender].title()} ({sender.title()})"

    def register(namespace: Dict[str, Any]) -> (Order, str):
        name = " ".join(namespace["name"]).lower()
        address_user = session.query(Participant).where(
            Participant.name == name).all()
        if address_user:
            return order, "User already registered"
        else:
            session.add(Participant(name=name))
            session.commit()
            return order, f"Added {name.title()}"

    def registered(*_) -> (Order, str):
        users = [(user.matrix_address, user.name) for user in session.query(Participant).all()]
        return order, "\n".join(str(user) for user in users)

    def reopen(*_) -> (Order, str):
        if order:
            return order, "Close current order first"
        last_order_id = session.query(DB_Order.oid).order_by(DB_Order.timestamp.desc()).first()
        if last_order_id is not None:
            last_order = session.query(DB_Order, Cuts, Participant) \
                .filter(DB_Order.oid == last_order_id[0]) \
                .filter(DB_Order.oid == Cuts.oid) \
                .filter(Cuts.pid == Participant.pid) \
                .all()
            if last_order:  # 0 -> order, 1 -> cut, 2 -> participiant
                new_order = Order()
                for cut in last_order:
                    if cut[1].name == "tip":
                        logging.debug(cut[1].name)
                        new_order.add_tip(cut[1].cut)
                        update_part(cut[2].pid, cut[1].cut, session)
                    elif cut[1].name != "paid amount":
                        logging.debug(cut[1].name)
                        new_order.add_pos(cut[2].matrix_address, cut[1].name, cut[1].cut)
                        update_part(cut[2].pid, cut[1].cut, session)
                for cut in last_order:
                    if cut[1].name == "paid amount":
                        logging.debug(cut[1].name)
                        # new_order.pay(cut[2].matrix_address)
                        update_part(cut[2].pid, cut[1].cut, session)
                logging.debug(new_order.order)
                session.delete(cut[0])
                session.commit()
                return new_order, new_order.print_order()
        return order, "No last order"

    def suggest(*_) -> (Order, str):
        last_orders = session.query(Cuts, Participant).filter(Participant.matrix_address == sender.lower()).filter(
            Cuts.pid == Participant.pid).filter(and_((Cuts.name != "paid amount"), (Cuts.name != "tip"))).order_by(
            Cuts.timestamp.desc()).limit(5).all()
        return order, f"As your last {len(last_orders)} order(s), you ordered: \n" + "\n".join(
            item[0].name + ", " + cent_to_euro(item[0].cut) for item in last_orders)

    def init(namespace: Dict[str, Any]) -> (Order, str):
        name = " ".join(namespace["name"]).lower()
        cur_user = find_match_in_database(name, session)
        if cur_user is None:
            return order, f"User {name.title()} not registered"
        bal = euro_to_cent(namespace["balance"])
        if cur_user.user_total == 0:
            session.add(
                Cuts(pid=cur_user.pid, cut=bal, name="initial balance")
            )
            session.commit()
            cur_user.user_total = bal
            session.commit()
            return order, f"Set init balance for {cur_user.name.title()} to {cent_to_euro(bal)}"
        else:
            return order, f"Balance of {cur_user.name.title()} is not zero, use 'balance' to check"

    def deinit(namespace: Dict[str, Any]) -> (Order, str):
        if namespace["self"]:
            cur_user = session.query(Participant).where(Participant.matrix_address == sender.lower()).first()
        else:
            name = " ".join(namespace["name"]).lower()
            cur_user = find_match_in_database(name, session)

        if cur_user is None:
            return order, f"User {sender.title()} not registered"
        elif cur_user.user_total != 0:
            return order, f"Balance of {cur_user.name.title()} is {cent_to_euro(cur_user.user_total)}"
        elif cur_user.user_total == 0:
            cur_user.is_active = False
            session.commit()
            return order, f"User {cur_user.name.title()} left..."

    order_parser = argparse.ArgumentParser(prog="UserBot", add_help=False, usage="%(prog)s options:")
    order_subparser = order_parser.add_subparsers()

    start_parser = order_subparser.add_parser(cmd[4], help="starts a new collective order")
    start_parser.set_defaults(func=start)
    start_parser.add_argument("name", nargs=argparse.ZERO_OR_MORE, default=["an", "unknown", "order"],
                              help="name of collective order")

    add_parser = order_subparser.add_parser(cmd[1], help="adds new order")
    add_parser.set_defaults(func=add)
    add_parser.add_argument("order name", type=str, nargs=argparse.ZERO_OR_MORE, default=["unknown", "Meal"],
                            help="name of order")
    add_parser.add_argument("price", type=float, help="price of order")
    add_parser.add_argument("--name", "-n", type=str,
                            help="orderer, if different from messenger, in quotes")

    tip_parser = order_subparser.add_parser(cmd[3], help="adds a tip")
    tip_parser.set_defaults(func=tip)
    tip_parser.add_argument("tip", type=float, help="tip amount")

    remove_parser = order_subparser.add_parser(cmd[2], help="removes order from collective order")
    remove_parser.set_defaults(func=remove)
    remove_parser.add_argument("--name", "-n", type=str, nargs=argparse.ONE_OR_MORE,
                               help="orderer, if different from messenger")
    remove_parser.add_argument("--all", "-a", action='store_true',
                               help="flag indicates, that all orders from orderer are removed")
    remove_parser.add_argument("--order", "-o", nargs=argparse.ZERO_OR_MORE,
                               help="name of order, otherwise all are removed (see -a flag)")

    end_parser = order_subparser.add_parser(cmd[6], help="finishes collective order")
    end_parser.set_defaults(func=pay)
    end_parser.add_argument("--name", "-n", type=str, nargs=argparse.ONE_OR_MORE,
                            help="payer, if different from messenger")
    end_parser.add_argument("--amount", "-a", type=float,
                            help="amount paid, if not specified, everything is paid, and the order is finished")

    cancel_parser = order_subparser.add_parser(cmd[5], help="cancels current collective order")
    cancel_parser.set_defaults(func=cancel)

    print_parser = order_subparser.add_parser(cmd[7], help="displays current collective order")
    print_parser.set_defaults(func=print_order)
    print_parser.add_argument("--self", "-s", action='store_true', help="displays only the orders of the messenger")

    reopen_parser = order_subparser.add_parser(cmd[13])  # help="reopens last order, if no current order"
    reopen_parser.set_defaults(func=reopen)

    user_parser = argparse.ArgumentParser(prog="UserBot", add_help=False, usage="%(prog)s options:")
    user_subparser = user_parser.add_subparsers()

    register_parser = user_subparser.add_parser(cmd[0], help="registers different user, use join to register yourself")
    register_parser.set_defaults(func=register)
    register_parser.add_argument("name", nargs=argparse.ONE_OR_MORE, type=str)

    payout_parser = user_subparser.add_parser(cmd[8], help="pays out the remaining debt/due balance of messenger")
    payout_parser.set_defaults(func=payout)
    payout_parser.add_argument("--name", "-n", type=str, nargs=argparse.ONE_OR_MORE,
                               help="orderer, if different from messenger")

    add_money_parser = user_subparser.add_parser(cmd[9], help="adds initial balance", prefix_chars="@")
    add_money_parser.set_defaults(func=add_money)
    add_money_parser.add_argument("name", nargs=argparse.ONE_OR_MORE, type=str, help="recipient")
    add_money_parser.add_argument("balance", type=float, help="balance")

    balance_parser = user_subparser.add_parser(cmd[10], help="displays the balance of all users")
    balance_parser.set_defaults(func=balance)

    join_parser = user_subparser.add_parser(cmd[11], help="joins system")
    join_parser.add_argument("--all", "-a", action='store_true', help="adds all current members of the room to the db")
    join_parser.set_defaults(func=join)

    registered_parser = user_subparser.add_parser(cmd[12])
    registered_parser.set_defaults(func=registered)

    suggest_parser = user_subparser.add_parser(cmd[14], help="returns the last 5 orders, with pricing")
    suggest_parser.set_defaults(func=suggest)

    main_parser = argparse.ArgumentParser(prog="OrderBot", add_help=False, usage="%(prog)s options:")
    main_subparser = main_parser.add_subparsers()

    order_parser = main_subparser.add_parser("order", parents=[order_parser], help="manages orders")
    order_parser.add_argument("order", action="store_true", help="manages orders")
    user_parser = main_subparser.add_parser("users", parents=[user_parser], help="manages users")
    user_parser.add_argument("users", action="store_true", help="manages users")

    init_parser = user_subparser.add_parser(cmd[15], help="initializes user")
    init_parser.set_defaults(func=init)
    init_parser.add_argument("name", nargs=argparse.ONE_OR_MORE, type=str, help="name of user")
    init_parser.add_argument("balance", type=float, help="balance")

    deinit_parser = user_subparser.add_parser(cmd[16], help="deinitializes user, if balance is zero")
    deinit_parser.set_defaults(func=deinit)
    deinit_parser.add_argument("--self", "-s", action='store_true', help="deinitializes messenger")
    deinit_parser.add_argument("name", nargs=argparse.ZERO_OR_MORE, type=str, help="name of user")

    try:
        args = main_parser.parse_args(inp)
        logging.debug(args)
        result = args.func(vars(args))
        return result

    # eror handling for wrong input or help command
    except (SystemExit, AttributeError):
        if inp[0] in ["order", "users"]:
            if len(inp) > 1 and inp[1] in cmd and inp[0] == "order":
                possible_parsers = [action for action in order_parser._actions if
                                    isinstance(action, argparse._SubParsersAction)]
                for parser_action in possible_parsers:
                    for choice, subparser in parser_action.choices.items():
                        if choice == inp[1]:
                            return order, subparser.format_help()
            elif len(inp) > 1 and inp[1] in cmd and inp[0] == "users":
                possible_parsers = [action for action in user_parser._actions if
                                    isinstance(action, argparse._SubParsersAction)]
                for parser_action in possible_parsers:
                    for choice, subparser in parser_action.choices.items():
                        if choice == inp[1]:
                            return order, subparser.format_help()
            else:
                possible_parsers = [action for action in main_parser._actions if
                                    isinstance(action, argparse._SubParsersAction)]
                for parser_action in possible_parsers:
                    for choice, subparser in parser_action.choices.items():
                        if choice == inp[0]:
                            return order, subparser.format_help()

        else:
            return order, main_parser.format_help()

    # error handling for database errors
    except SQLAlchemyError as e:
        logging.error(e)
        return order, "SQLAlchemy error, see logs for more info"
