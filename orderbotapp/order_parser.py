import argparse
import random
import re
from decimal import Decimal, ROUND_HALF_DOWN

from sqlalchemy import or_, update

from order import Order
from orderbotapp.db_classes import Participant, Cuts

cmd = [
    "user",  # add user
    "add",  # add pos to order
    "remove",  # add all pos from given user
    "tip",  # add tip
    "start",  # start new order
    "cancel",  # cancel order
    "end",  # end order and distribute cut
    "print",
    "payout"
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
    all_registered_users = [name for nametuple in session.query(Participant.name, Participant.matrix_address).all() for
                            name in nametuple]
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
            else:
                session.add(Participant(name=user))
            session.commit()

        user_id = session.query(Participant.pid) \
            .where(or_(Participant.name == user, Participant.matrix_address == user)) \
            .first()[0]
        user_tip = tip_shares[index]
        session.add(
            Cuts(pid=user_id, oid=db_order.oid, cut=sum(item[1] for item in order.order[user]) + user_tip))
        session.commit()

        # update owned ect.
        session.execute(
            update(Participant).where(Participant.pid == user_id)
                .values(user_total=Participant.user_total + sum(item[1] for item in order.order[user]) + user_tip)
        )


def no_active_order():
    """
    simple method to streamline reply-message
    """
    return None, "start an order first!"


def parse_input(inp, session, order, sender):
    def add(namespace):
        order_to_return = order
        msg = ""
        price = euro_to_cent(namespace['price'])
        if namespace["name"] is None:
            name = sender
        else:
            name = namespace["name"]
        if order_to_return is None:
            order_to_return, msg = start({"name": "an unnamed order"})
            msg = msg + "\n"
        meal_name = " ".join(namespace["order name"])
        order_to_return.add_pos(user=name, item=meal_name, amount=price)
        return order_to_return, msg + f"Order added for {name}, order: {meal_name}, price: {cent_to_euro(price)}"

    def user(*_):
        return order, "I am just a stub"

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
            if sender in order.order:
                return order, order.print_order(sender)
            else:
                return order, f"{sender} not in current order"
        else:
            return order, order

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
            name = sender
        else:
            name = namespace["name"]

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
            name = sender
        else:
            name = namespace["name"]
        if namespace["amount"] is None or namespace["amount"] * 100 >= order.price + order.tip:
            order.pay(name)
            save_order_in_db(order, session)
            return None, "order paid\n" + str(order)
        elif namespace["amount"] > 0:
            amount = euro_to_cent(namespace['amount'])
            order.pay(name, amount)
            return order, f"{cent_to_euro(amount)} of order {order.name} paid."
        else:
            return order, "amount has to be positive"

    def payout(namespace):

        cur_user = session.query(Participant).where(Participant.matrix_address == sender).first()
        debt = cur_user.user_total
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
                    session.execute(
                        update(Participant).where(Participant.pid == user.pid)
                            .values(user_total=min(user.user_total + debt, 0))
                    )
                    diffs.append((user.pid, user.user_total - min(user.user_total + debt, 0)))
                    debt = max(debt + user.user_total, 0)
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
                return order, f"{sender}, pay:\n" + "\n".join(f"{item[0]} : {- item[1]}" for item in diffs)

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
                    session.execute(
                        update(Participant).where(Participant.pid == user.pid)
                            .values(user_total=max(user.user_total + debt, 0))
                    )
                    diffs.append((user.pid, user.user_total - max(user.user_total + debt, 0)))
                    debt = min(debt + user.user_total, 0)
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
                return order, f"{sender}, receive from:\n" + "\n".join(f"{item[0]} : {item[1]}" for item in diffs)
        else:
            return order, "Nothing to payout"

    order_parser = argparse.ArgumentParser(prog="OrderBot", add_help=False, usage="%(prog)s options:")
    subparser = order_parser.add_subparsers()

    start_parser = subparser.add_parser(cmd[4], help="starts a new collective order")
    start_parser.set_defaults(func=start)
    start_parser.add_argument("name", nargs=argparse.ZERO_OR_MORE, default=None, help="name of collective order")

    add_parser = subparser.add_parser(cmd[1], help="adds new order")
    add_parser.set_defaults(func=add)
    add_parser.add_argument("--name", "-n", type=str, help="orderer, if different from messenger")
    add_parser.add_argument("order name", type=str, nargs=argparse.ZERO_OR_MORE, default=["unknown", "Meal"],
                            help="name of order")
    add_parser.add_argument("price", type=float, help="price of order")

    tip_parser = subparser.add_parser(cmd[3], help="adds a tip")
    tip_parser.set_defaults(func=tip)
    tip_parser.add_argument("tip", type=float, help="tip amount")

    remove_parser = subparser.add_parser(cmd[2], help="remove order from collective order")
    remove_parser.set_defaults(func=remove)
    remove_parser.add_argument("--name", "-n", type=str, help="orderer, if different from messenger")
    remove_parser.add_argument("--all", "-a", action='store_true',
                               help="flag indicates, that all orders from orderer are removed")
    remove_parser.add_argument("--order", "-o", nargs=argparse.ZERO_OR_MORE,
                               help="name of order, otherwise all are removed (see -a flag)")

    end_parser = subparser.add_parser(cmd[6], help="finish collective order")
    end_parser.set_defaults(func=pay)
    end_parser.add_argument("--name", "-n", type=str, help="payer, if different from messenger")
    end_parser.add_argument("--amount", "-a", type=float,
                            help="amount paid, if not specified, everything is paid, and the order is finished")

    cancel_parser = subparser.add_parser(cmd[5], help="cancels current collective order")
    cancel_parser.set_defaults(func=cancel)

    """
    user_parser = subparser.add_parser(cmd[0], help=argparse.SUPPRESS)
    user_parser.set_defaults(func=user)
    user_parser.add_argument("--name", "-n", type=str)
    """

    print_parser = subparser.add_parser(cmd[7], help="displays current collective order")
    print_parser.set_defaults(func=print_order)
    print_parser.add_argument("--self", "-s", action='store_true', help="displays only the orders of the messager")

    payout_parser = subparser.add_parser(cmd[8], help="let user payout there remaining debt/due balance")
    payout_parser.set_defaults(func=payout)

    try:
        args = order_parser.parse_args(inp)
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
