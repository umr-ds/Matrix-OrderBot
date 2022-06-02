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
        return True, order_to_return, msg + f"Order added for {name}, order: {meal_name}, price: {namespace['price']}"

    def start(namespace):
        if order is None:
            if namespace["name"] is None or namespace["name"] == []:
                return True, Order(), "Started new Order"
            else:
                return True, Order(" ".join(namespace["name"])), "Started new Order with Name: " + " ".join(
                    namespace["name"])
        else:
            return True, order, "Finish current order first"

    def cancel(*_):
        return True, None, "Cancelled current order"

    def tip(namespace):
        ttip = namespace["tip"]
        if ttip > 0:
            order.add_tip(ttip)
            return True, order, f"Added tip {ttip}"
        else:
            return True, order, f"negative tip"

    def remove(namespace):
        remove_all = namespace["all"]
        order_to_remove = namespace["order"]
        if namespace["name"] is None:
            name = sender
        else:
            name = namespace["name"]

        if remove_all or order_to_remove is None:
            order.remove(name)
            return True, order, f"Removed user {name} from order"
        else:
            order.remove(name, order_to_remove)
            return True, order, f"Removed order {order} for {name} from order"

    def pay(namespace):
        if namespace["name"] is None:
            name = sender
        else:
            name = namespace["name"]
        if namespace["amount"] is None or namespace["amount"] >= order.price + order.tip:
            order.pay(name)
            return True, None, "msg"
        else:
            order.pay(name, namespace["amount"])
            return True, order, "msg"

    order_parser = argparse.ArgumentParser(prog="OrderBot", add_help=False, usage="%(prog)s options:")
    subparser = order_parser.add_subparsers()

    add_parser = subparser.add_parser(cmd[1], help="adds order")
    add_parser.set_defaults(func=add)
    add_parser.add_argument("--name", "-n", type=str)
    add_parser.add_argument("meal-name", type=str, nargs=argparse.ZERO_OR_MORE, default=["unknown", "Meal"])
    add_parser.add_argument("price", type=float)

    start_parser = subparser.add_parser(cmd[4], help="starts a new order")
    start_parser.set_defaults(func=start)
    start_parser.add_argument("name", nargs=argparse.ZERO_OR_MORE, default=None)

    abort_parser = subparser.add_parser(cmd[5], help="cancels current order")
    abort_parser.set_defaults(func=cancel)

    user_parser = subparser.add_parser(cmd[0], help="adds user to system")
    user_parser.set_defaults(func=user)
    user_parser.add_argument("--name", "-n", type=str)

    tip_parser = subparser.add_parser(cmd[3], help="added tip to order")
    tip_parser.set_defaults(func=tip)
    tip_parser.add_argument("tip", type=float)

    remove_parser = subparser.add_parser(cmd[2], help="remove pos from order")
    remove_parser.set_defaults(func=remove)
    remove_parser.add_argument("--name", "-n", type=str)
    remove_parser.add_argument("--all", "-a", action='store_true')
    remove_parser.add_argument("--order", "-o", nargs=argparse.ZERO_OR_MORE)

    end_parser = subparser.add_parser(cmd[6], help="finish order")
    end_parser.set_defaults(func=pay)
    end_parser.add_argument("--name", "-n", type=str)
    end_parser.add_argument("--amount", "-a", type=float)

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
                        return False, order, subparser.format_help()
        else:
            False, order, order_parser.format_help()