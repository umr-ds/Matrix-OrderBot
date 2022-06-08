import argparse
import random
import re
from decimal import Decimal, ROUND_HALF_DOWN

from order import Order

cmd = [
    "user",  # add user
    "add",  # add pos to order
    "remove",  # add all pos from given user
    "tip",  # add tip
    "start",  # start new order
    "cancel",  # cancel order
    "end"  # end order and distribute cut
]


def to_currency_decimal(f):
    return Decimal(f).quantize(Decimal('0.01'), rounding=ROUND_HALF_DOWN)


def split_tip(tip, number_of_shares):
    l = [int(tip * 100) // number_of_shares] * number_of_shares
    too_much = int(tip * 100 - sum(l))
    if too_much > 0:
        for i in range(too_much):
            l[i] = l[i] + 1
    if too_much < 0:
        for i in range(-too_much):
            l[i] = l[i] - 1
    random.shuffle(l)
    return [to_currency_decimal(x / 100) for x in l]


def save_order_in_db(order, conn, cur):
    # register all user in db, if not already in there.
    cur.execute("SELECT name, username from participant")
    all_registered_users = [item for tup in cur.fetchall() for item in tup]

    # add order into db
    cur.execute("SELECT nextval(pg_get_serial_sequence('orders', 'order_id'))")
    cut_id = cur.fetchone()[0]
    cur.execute("INSERT INTO orders(order_id, total, price, tip, name, timestamp) values (%s, %s, %s, %s, %s, now())",
                (cut_id, order.price + order.tip, order.price, order.tip, order.name))
    conn.commit()

    tip_shares = split_tip(order.tip, len(order.order))
    # adding all users to participant, cuts
    for index, user in enumerate(order.order):
        if user not in all_registered_users:
            handle = re.match(r"@(\S+):\S+\.\S+", user)
            if handle:
                name = handle.group(1)
                cur.execute("INSERT INTO participant(name,username) VALUES (%s, %s)", (name, user))
            else:
                cur.execute("INSERT INTO participant(name) VALUES (%s)", (user,))
            conn.commit()

        cur.execute("SELECT id from participant where username = %s or name = %s", (user, user))
        user_id = cur.fetchone()[0]

        user_tip = tip_shares[index]
        cur.execute("INSERT INTO cuts(order_id, id, cut, timestamp) VALUES (%s, %s, %s, now())",
                    (cut_id, user_id, sum(item[1] for item in order.order[user]) + user_tip))
        conn.commit()

        # update owned ect.
        cur.execute("UPDATE participant SET user_total = user_total + %s where id = %s",
                    (sum(item[1] for item in order.order[user]) + user_tip, user_id))
        conn.commit()


def parse_input(inp, connection, cursor, order, sender):
    def add(namespace):
        order_to_return = order
        msg = ""
        price = to_currency_decimal(namespace['price'])
        if namespace["name"] is None:
            name = sender
        else:
            name = namespace["name"]
        if order_to_return is None:
            order_to_return, msg = start({"name": "an unnamed order"})
            msg = msg + "\n"
        meal_name = " ".join(namespace["order name"])
        order_to_return.add_pos(user=name, item=meal_name, amount=price)
        return order_to_return, msg + f"Order added for {name}, order: {meal_name}, price: {price}"

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

    def tip(namespace):
        if order is None:
            return None, "start an order first!"
        ttip = to_currency_decimal(namespace['tip'])
        if ttip > 0:
            order.add_tip(ttip)
            return order, f"Added tip: {ttip}"
        else:
            return order, f"negative tip"

    def remove(namespace):
        if order is None:
            return None, "start an order first!"
        remove_all = namespace["all"]
        order_to_remove = namespace["order"]
        if namespace["name"] is None:
            name = sender
        else:
            name = namespace["name"]

        if remove_all or order_to_remove is None:
            order.remove(name, connection, cursor)
            return order, f"Removed user {name} from order"
        else:
            order.remove(name, order_to_remove)
            return order, f"Removed order {namespace['order']} for {name} from order"

    def pay(namespace):
        if order is None:
            return None, "start an order first!"
        if namespace["name"] is None:
            name = sender
        else:
            name = namespace["name"]
        if namespace["amount"] is None or namespace["amount"] >= order.price + order.tip:
            order.pay(name)
            save_order_in_db(order, connection, cursor)
            return None, "order paid\n" + str(order)
        elif namespace["amount"] > 0:
            amount = to_currency_decimal(namespace['amount'])
            order.pay(name, amount)
            return order, f"{amount} of order {order.tip + order.price} paid."
        else:
            return order, "amount has to be positive"

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
