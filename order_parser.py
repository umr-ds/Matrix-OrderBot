import re
import config
from order import Order
import argparse

cmd = config.commands


def parse_input(inp, connection, cursor, order, sender):

    def add(namespace):
        orderToReturn = order
        if namespace["name"] is None:
            name = sender
        else:
            name = namespace["name"]
        if orderToReturn is None:
            orderToReturn = Order()
        meal_name = " ".join([part for part in namespace["meal-name"]])
        print(name, meal_name, namespace["price"])
        orderToReturn.add_pos(user=name, item=meal_name, amount=namespace["price"])
        return True, orderToReturn, f"Order added for {name}, order: {meal_name}, price: {namespace['price']}"


    orderParser = argparse.ArgumentParser()
    subparser = orderParser.add_subparsers()

    add_parser = subparser.add_parser(cmd[1], help="adds order")
    add_parser.set_defaults(func=add)
    add_parser.add_argument("--name", "-n", type=str)
    add_parser.add_argument("meal-name", type=str, nargs=argparse.ZERO_OR_MORE, default=["unknown", "Meal"])
    add_parser.add_argument("price", type=float)

    try:
        args = orderParser.parse_args(inp)
        result = args.func(vars(args))
        print(result)
        return result
    except SystemExit:
        return False, None, "SystemExit"