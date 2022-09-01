import argparse
import logging
import random
import re
from decimal import Decimal, ROUND_HALF_DOWN

from sqlalchemy import or_, update

from db_classes import Participant, Cuts, DB_Order
from order import Order

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
    "init",
    "balance",
    "join",
    "all",
    "reopen",
    "reorder"
]


def cent_to_euro(cents):
    return "{:.2f}".format(cents / 100)


def euro_to_cent(f):
    return int(Decimal(f * 100).quantize(Decimal('1'), rounding=ROUND_HALF_DOWN))


def split_tip(tip, number_of_shares):
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


def save_order_in_db(order, session):
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
                .values(user_total=Participant.user_total + sum(item[1] for item in order.order[user]) + user_tip)
        )
        session.commit()


def no_active_order():
    """
    simple method to streamline reply-message
    """
    return None, "start an order first!"


def check_name_in_db(name, session):
    return session.query(Participant).where(Participant.name == name.lower()).first()


def check_address_in_db(address, session):
    return session.query(Participant).where(Participant.matrix_address == address.lower()).first()


def parse_input(inp, session, order, sender, members):
    def add(namespace):
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
        return order_to_return, msg + f"Order added for {name}, order: {meal_name}, price: {cent_to_euro(price)}"

    def start(namespace):
        if order is None:
            if namespace["name"] is None or namespace["name"] == []:
                return Order(), "Started new collective order"
            else:
                return Order(" ".join(namespace["name"])), "Started new collective order with Name: " + " ".join(
                    namespace["name"])
        else:
            return order, "finish current collective order first"

    def cancel(*_):
        return None, "Cancelled current collective order"

    def print_order(namespace):
        if order is None:
            return no_active_order()
        if namespace["self"]:
            name = members[sender].lower()
            if name in order.order:
                return order, order.print_order(name)
            else:
                return order, f"{name} not in current order"
        else:
            return order, order.print_order()

    def tip(namespace):
        if order is None:
            return no_active_order()
        ttip = euro_to_cent(namespace['tip'])
        if ttip > 0:
            order.add_tip(ttip)
            return order, f"Added tip: {cent_to_euro(ttip)}"
        else:
            return order, f"negative tip"

    def remove(namespace):
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
            return order, f"Removed user {name} from order"
        else:
            order.remove(name, order_to_remove)
            return order, f"Removed order {namespace['order']} for {name} from order"

    def pay(namespace):
        if order is None:
            return no_active_order()
        if namespace["name"] is None:
            p = check_address_in_db(sender, session)
            if not p:
                return order, "Register user first with !ob join"
            name = p.name
        else:
            p = check_name_in_db(sender, session)
            if not p:
                return order, "Register user first with !ob register <name>"
            name = p.name
        if namespace["amount"] is None:
            order.pay(name)
            save_order_in_db(order, session)
            return None, "order paid\n" + str(order)
        elif namespace["amount"] * 100 >= order.price + order.tip:
            order.add_tip(namespace["amount"] * 100 - order.price + order.tip)
            order.pay(name)
            save_order_in_db(order, session)
            return None, "order paid\n" + str(order)
        else:
            return order, f"amount must be greater than {cent_to_euro(order.price + order.tip)}"

    def payout(namespace):
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
                return order, f"{name} pay =>\n" + "\n".join(f"{item[0]} : {cent_to_euro(- item[1])}" for item in diffs)

            elif debt < 0:
                all_user = session.query(Participant).where(Participant.user_total > 0).order_by(
                    Participant.user_total.desc()).all()
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
                return order, f"{name} receives from <= \n" + "\n".join(
                    f"{item[0]} : {cent_to_euro(item[1])}" for item in diffs)
        else:
            return order, "Nothing to payout"

    def init(namespace):
        name = " ".join(namespace["name"]).lower()
        handle = re.match(r"@(\S+):\S+\.\S+", name)
        if handle:
            cur_user = session.query(Participant).where(Participant.matrix_address == name).first()
        else:
            cur_user = session.query(Participant).where(Participant.name == name).first()
        if cur_user is None:
            return order, f"user {name} not registered"
        bal = euro_to_cent(namespace["balance"])
        cur_user.user_total = cur_user.user_total + bal
        session.commit()
        return order, f"added {cent_to_euro(bal)} to {cur_user.name}"

    def balance(*_):
        all_balance = session.query(Participant.name, Participant.matrix_address, Participant.user_total).order_by(
            Participant.user_total.desc()).all()
        msg = "Current balances: \n"
        msg = msg + "\n".join([f"{user.name} ({user.matrix_address}):\t {user.user_total}" for user in all_balance])
        return order, msg

    def join(namespace):
        if namespace["all"]:
            users = [user.matrix_address for user in session.query(Participant).all()]
            added_users = []
            for user in members:
                if user not in users:
                    session.add(Participant(matrix_address=user.lower(), name=members[user].lower()))
                    added_users.append(user)
            session.commit()
            if not added_users:
                ret = "not user added"
            else:
                ret = "\n".join([f"added {user}:{members[user]}" for user in added_users])
            return order, ret
        else:
            user = session.query(Participant).where(Participant.matrix_address == sender.lower()).all()
            if user:
                return order, "user already registered"
            else:
                session.add(Participant(matrix_address=sender.lower(), name=members[sender].lower()))
                session.commit()
                return order, f"added {members[sender]} ({sender})"

    def register(namespace):
        name = " ".join(namespace["name"]).lower()
        address_user = session.query(Participant).where(
            Participant.name == name).all()
        if address_user:
            return order, "user already registered"
        else:
            session.add(Participant(name=name))
            session.commit()
            return order, f"added {name}"

    def registered(*_):
        users = [(user.matrix_address, user.name) for user in session.query(Participant).all()]
        return order, "\n".join(str(user) for user in users)

    def reopen(*_):
        if order:
            return order, "close current order first"
        last_order_id = session.query(DB_Order.oid).order_by(DB_Order.timestamp.desc()).first()
        if last_order_id is not None:
            last_order = session.query(DB_Order, Cuts, Participant) \
                .filter(DB_Order.oid == last_order_id[0]) \
                .filter(DB_Order.oid == Cuts.oid) \
                .filter(Cuts.pid == Participant.pid) \
                .all()
            if last_order:  # 0 -> order, 1 -> cut, 2 -> participiant
                return order, "\n".join(
                    [str(cut[1].name) + "," + str(cut[2].name) + "," + str(cut[1].cut) + "," + str(
                        last_order_id) + "," + str(
                        cut[0].oid) for cut in
                     last_order])
        return order, "stub"

    def reorder(*_):
        return order, "stub"

    order_parser = argparse.ArgumentParser(prog="OrderBot", add_help=False, usage="%(prog)s options:")
    subparser = order_parser.add_subparsers()

    start_parser = subparser.add_parser(cmd[4], help="starts a new collective order")
    start_parser.set_defaults(func=start)
    start_parser.add_argument("name", nargs=argparse.ZERO_OR_MORE, default=["an", "unknown", "order"],
                              help="name of collective order")

    add_parser = subparser.add_parser(cmd[1], help="adds new order")
    add_parser.set_defaults(func=add)
    add_parser.add_argument("order name", type=str, nargs=argparse.ZERO_OR_MORE, default=["unknown", "Meal"],
                            help="name of order")
    add_parser.add_argument("price", type=float, help="price of order")
    add_parser.add_argument("--name", "-n", type=str,
                            help="orderer, if different from messenger, in quotes")

    tip_parser = subparser.add_parser(cmd[3], help="adds a tip")
    tip_parser.set_defaults(func=tip)
    tip_parser.add_argument("tip", type=float, help="tip amount")

    remove_parser = subparser.add_parser(cmd[2], help="removes order from collective order")
    remove_parser.set_defaults(func=remove)
    remove_parser.add_argument("--name", "-n", type=str, nargs=argparse.ONE_OR_MORE,
                               help="orderer, if different from messenger")
    remove_parser.add_argument("--all", "-a", action='store_true',
                               help="flag indicates, that all orders from orderer are removed")
    remove_parser.add_argument("--order", "-o", nargs=argparse.ZERO_OR_MORE,
                               help="name of order, otherwise all are removed (see -a flag)")

    end_parser = subparser.add_parser(cmd[6], help="finishes collective order")
    end_parser.set_defaults(func=pay)
    end_parser.add_argument("--name", "-n", type=str, nargs=argparse.ONE_OR_MORE,
                            help="payer, if different from messenger")
    end_parser.add_argument("--amount", "-a", type=float,
                            help="amount paid, if not specified, everything is paid, and the order is finished")

    cancel_parser = subparser.add_parser(cmd[5], help="cancels current collective order")
    cancel_parser.set_defaults(func=cancel)

    register_parser = subparser.add_parser(cmd[0], help="registers different user, use join to register yourself")
    register_parser.set_defaults(func=register)
    register_parser.add_argument("name", nargs=argparse.ONE_OR_MORE, type=str)

    print_parser = subparser.add_parser(cmd[7], help="displays current collective order")
    print_parser.set_defaults(func=print_order)
    print_parser.add_argument("--self", "-s", action='store_true', help="displays only the orders of the messenger")

    payout_parser = subparser.add_parser(cmd[8], help="pays out the remaining debt/due balance of messenger")
    payout_parser.set_defaults(func=payout)
    payout_parser.add_argument("--name", "-n", type=str, nargs=argparse.ONE_OR_MORE,
                               help="orderer, if different from messenger")

    init_parser = subparser.add_parser(cmd[9], help="adds initial balance", prefix_chars="@")
    init_parser.set_defaults(func=init)
    init_parser.add_argument("name", nargs=argparse.ONE_OR_MORE, type=str, help="recipient")
    init_parser.add_argument("balance", type=float, help="balance")

    balance_parser = subparser.add_parser(cmd[10], help="displays the balance of all users")
    balance_parser.set_defaults(func=balance)

    join_parser = subparser.add_parser(cmd[11], help="joins system")
    join_parser.add_argument("--all", "-a", action='store_true', help="adds all current members of the room to the db")
    join_parser.set_defaults(func=join)

    registered_parser = subparser.add_parser(cmd[12])
    registered_parser.set_defaults(func=registered)

    reopen_parser = subparser.add_parser(cmd[13], help="reopens last order, if no current order")
    reopen_parser.set_defaults(func=reopen)

    try:
        args = order_parser.parse_args(inp)
        logging.debug(args)
        result = args.func(vars(args))
        return result
    except SystemExit:
        if inp[0] in cmd:
            possible_parsers = [action for action in order_parser._actions if
                                isinstance(action, argparse._SubParsersAction)]
            for parser_action in possible_parsers:
                for choice, subparser in parser_action.choices.items():
                    if choice == inp[0]:
                        return order, subparser.format_help()
        else:
            return order, order_parser.format_help()
