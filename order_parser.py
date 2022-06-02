import config
from order import Order
import argparse

cmd = config.commands

def parse_input(inp, connection, cursor, order, sender):
    def add(namespace):
        order_to_return = order
        msg = ""
        if namespace["name"] is None:
            name = sender
        else:
            name = namespace["name"]
        if order_to_return is None:
            _, order_to_return, msg = start({"name": None})
            msg = msg + "\n"
        meal_name = " ".join(namespace["meal-name"])
        print(name, meal_name, namespace["price"])
        order_to_return.add_pos(user=name, item=meal_name, amount=namespace["price"])
        return order_to_return, msg + f"Order added for {name}, order: {meal_name}, price: {namespace['price']}"

    def user(*_):
        return order, "I am just a stub"

    def start(namespace):
        if order is None:
            if namespace["name"] is None or namespace["name"] == []:
                return Order(), "Started new Order"
            else:
                return Order(" ".join(namespace["name"])), "Started new Order with Name: " + " ".join(
                    namespace["name"])
        else:
            return order, "Finish current order first"

    def cancel(*_):
        return None, "Cancelled current order"

    def tip(namespace):
        if order is None:
            return None, "start an Order first!"
        ttip = namespace["tip"]
        if ttip > 0:
            order.add_tip(ttip)
            return order, f"Added tip {ttip}"
        else:
            return order, f"negative tip"

    def remove(namespace):
        if order is None:
            return None, "start an Order first"
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
            return order, f"Removed order {order} for {name} from order"

    def pay(namespace):
        if order is None:
            return None, "Start an order first"
        if namespace["name"] is None:
            name = sender
        else:
            name = namespace["name"]
        if namespace["amount"] is None or namespace["amount"] >= order.price + order.tip:
            order.pay(name)
            return None, "Order paid\n" + order
        else:
            order.pay(name, namespace["amount"])
            return order, f"{namespace[amount]} of order {order.tip + order.price} paid. (Debug, show remaining.)"

    order_parser = argparse.ArgumentParser(prog="OrderBot", add_help=False, usage="%(prog)s options:")
    subparser = order_parser.add_subparsers()

    add_parser = subparser.add_parser(cmd[1], help="adds order")
    add_parser.set_defaults(func=add)
    add_parser.add_argument("--name", "-n", type=str, help="orderer, if different from sender")
    add_parser.add_argument("order name", type=str, nargs=argparse.ZERO_OR_MORE, default=["unknown", "Meal"], help="name of order")
    add_parser.add_argument("price", type=float, help="price of order")

    start_parser = subparser.add_parser(cmd[4], help="starts a new order")
    start_parser.set_defaults(func=start)
    start_parser.add_argument("name", nargs=argparse.ZERO_OR_MORE, default=None, help="name of order")

    abort_parser = subparser.add_parser(cmd[5], help="cancels current order")
    abort_parser.set_defaults(func=cancel)

    user_parser = subparser.add_parser(cmd[0], help=argparse.SUPPRESS)
    user_parser.set_defaults(func=user)
    user_parser.add_argument("--name", "-n", type=str)

    tip_parser = subparser.add_parser(cmd[3], help="added tip to order")
    tip_parser.set_defaults(func=tip)
    tip_parser.add_argument("tip", type=float, help="tip amount")

    remove_parser = subparser.add_parser(cmd[2], help="remove pos from order")
    remove_parser.set_defaults(func=remove)
    remove_parser.add_argument("--name", "-n", type=str, help="orderer, if different from sender")
    remove_parser.add_argument("--all", "-a", action='store_true', help="if this flag is set, all orders from current orderer are removed")
    remove_parser.add_argument("--order", "-o", nargs=argparse.ZERO_OR_MORE, help="name of order, otherwise all are removed (see -a flag)")

    end_parser = subparser.add_parser(cmd[6], help="finish order")
    end_parser.set_defaults(func=pay)
    end_parser.add_argument("--name", "-n", type=str, help="payer, if different from sender")
    end_parser.add_argument("--amount", "-a", type=float, help="amount paid, if not specified, everything is paid, and the order is finished")

    try:
        args = order_parser.parse_args(inp)
        result = args.func(vars(args))
        print(result)
        return result
    except SystemExit:
        if inp[0] in cmd:
            possible_parsers = [action for action in order_parser._actions if isinstance(action, argparse._SubParsersAction)]
            for parser_action in possible_parsers:
                for choice, subparser in parser_action.choices.items():
                    if choice == inp[0]:
                        return order, subparser.format_help()
        else:
            return order, order_parser.format_help()