import argparse
import collections
import logging
import traceback
from typing import Dict, Any

from sqlalchemy import and_
from sqlalchemy.exc import SQLAlchemyError

from orderbot.order import Order
from orderbot.orderbot import loglevel
from orderbot.util import *

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
    "edit",
    "reopen",
    "suggest",
    "init",
    "exit",
    "transfer",
    "reorder",
    "history",
]


def parse_input(inp: List[str], session: Session, order: Order, sender: str, members: Dict[str, str]) -> (Order, str):
    def add(namespace: Dict[str, Any]) -> (Order, str):
        logging.debug(namespace)
        order_to_return = order
        msg = ""
        price = euro_to_cent(namespace['price'])
        if namespace["name"] is None:
            p = find_match_in_database(sender, session, active=True)
            if not p:
                return order, "Register user first with !ob join"
            name = p.name
        else:
            p = find_match_in_database(namespace["name"], session, active=True)
            if not p:
                return order, "Register user first with !ob register <name>"
            name = p.name
        if order_to_return is None:
            order_to_return, msg = start({"name": ["an", "unnamed", "order"]})
            msg = msg + "\n"
        meal_name = " ".join(namespace["order name"])
        order_to_return.add_pos(user=name, item=meal_name, amount=price)
        return order_to_return, msg + f"Order added for {name.title()}, order: {meal_name}, price: {cent_to_euro(price)}"

    def edit(namespace: Dict[str, Any]) -> (Order, str):
        logging.debug(namespace)
        price = euro_to_cent(namespace['new price'])
        if namespace["name"] is None:
            p = find_match_in_database(sender, session, active=True)
            if not p:
                return order, "Register user first with !ob join"
            name = p.name
        else:
            p = find_match_in_database(namespace["name"], session, active=True)
            if not p:
                return order, "Register user first with !ob register <name>"
            name = p.name
        if order is None:
            return order, no_active_order()
        meal_name = " ".join(namespace["order name"])
        if order.edit_pos(user=name, item=meal_name, amount=price):
            return order, f"Order edited for {name.title()}, order: {meal_name}, price: {cent_to_euro(price)}"
        else:
            return order, f"Order not found for {name.title()}, order: {meal_name}"


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
            order.set_tip(ttip)
            return order, f"Set tip to {cent_to_euro(ttip)}"
        else:
            return order, f"negative tip"

    def remove(namespace: Dict[str, Any]) -> (Order, str):
        logging.debug(namespace)
        if order is None:
            return no_active_order()
        remove_all = namespace["all"]
        if namespace["name"] is None:
            name = members[sender].lower()
        else:
            name = " ".join(namespace["name"]).lower()

        if namespace["ordername"] is None:
            order_to_remove = None
        else:
            order_to_remove = " ".join(namespace["ordername"])

        if order_to_remove is None and not remove_all:
            order.remove(name)
            return order, f"Removed user {name.title()} from order"
        if remove_all:
            order.remove_all()
            return order, f"Removed all users from order"
        else:
            order.remove(name, order_to_remove)
            return order, f"Removed order {order_to_remove} for {name.title()} from order"

    def pay(namespace: Dict[str, Any]) -> (Order, str):
        if order is None:
            return no_active_order()
        if namespace["name"] is None:
            p = find_match_in_database(sender, session, active=True)
            if not p:
                return order, "Register user first with !ob join"
            name = p.name
        else:
            p = find_match_in_database(" ".join(namespace["name"]), session, active=True)
            if not p:
                return order, "Register user first with !ob register <name>"
            name = p.name
        if namespace["amount"] is None:
            order.pay(name)
            save_order_in_db(order, session)
            return None, "order paid\n" + str(order)
        elif euro_to_cent(namespace["amount"]) > 0:
            order.pay(name, euro_to_cent(namespace["amount"]))
            if order.paid:
                save_order_in_db(order, session)
                return None, "order paid\n" + str(order)
            else:
                return order, f"Order partially paid\n" + str(order)
        else:
            return order, f"amount must be positive"

    def reorder(namespace: Dict[str, Any]) -> (Order, str):
        if order is None:
            return order, "Start new order first"
        if not namespace["name"]:
            cur_user = find_match_in_database(sender, session, active=True)
        else:
            cur_user = find_match_in_database(" ".join(namespace["name"]).lower(), session)
        if cur_user is None:
            return order, "User not found"

        # order: order, Cuts, Participants
        last_order = session.query(DB_Order, Cuts, Participant).join(Cuts, Cuts.oid == DB_Order.oid).join(Participant,
                                                                                                          Cuts.pid == Participant.pid) \
            .filter(Participant.name == cur_user.name).filter(
            and_(Cuts.name != paid_string, Cuts.name != "tip")).order_by(DB_Order.oid.desc()).first()
        if last_order is None:
            return order, "No previous order found"
        else:
            namespace["name"] = cur_user.name
            namespace["order name"] = last_order.Cuts.name.split(" ")
            namespace["price"] = float(cent_to_euro(last_order.Cuts.cut))
            return add(namespace)

    def payout(namespace: Dict[str, Any]) -> (Order, str):
        if namespace["name"] is None:
            cur_user = find_match_in_database(sender, session, active=True)
            if not cur_user:
                return order, "User not registered"
        else:
            name = " ".join(namespace["name"]).lower()
            cur_user = find_match_in_database(name, session, active=True)
            if not cur_user:
                return order, "User not registered"
        debt = cur_user.user_total
        name = cur_user.name
        if debt != 0:
            if debt > 0:
                all_user = session.query(Participant).where(
                    and_(Participant.user_total < 0, Participant.is_active)).order_by(
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
                    diffs.append((user, user_bal - change))

                    debt = max(debt + user_bal, 0)
                session.commit()
                if debt > 0:
                    tup = diffs[0]
                    diffs[0] = (tup[0], tup[1] - debt)

                # formatting stuff
                max_name_len = max(len(item[0].name) for item in diffs)

                if namespace["accept"]:
                    for diff in diffs:
                        user = diff[0]
                        user_diff = diff[1]
                        user_bal = user.user_total
                        session.execute(
                            update(Participant).where(Participant.pid == user.pid)
                            .values(user_total=user_bal - user_diff)
                        )
                        cut = Cuts(pid=user.pid, cut=- user_diff, name="payout from " + str(cur_user.pid))
                        session.add(cut)

                    cut = Cuts(pid=cur_user.pid, cut=-cur_user.user_total, name="payout")
                    session.add(cut)
                    session.execute(
                        update(Participant).where(Participant.pid == cur_user.pid)
                        .values(user_total=0)
                    )
                    session.commit()
                    return order, f"{name.title()} receives from <=\n" + "\n".join(
                        f"{item[0].name.title():<{max_name_len}}: {cent_to_euro(- item[1])}" for item in diffs)
                else:
                    return order, f"possible transactions:\n{name.title()} receives from <=\n" + "\n".join(
                        f"{item[0].name.title():<{max_name_len}}: {cent_to_euro(- item[1])}" for item in diffs)

            elif debt < 0:
                all_user = session.query(Participant).where(
                    and_(Participant.user_total > 0, Participant.is_active)).order_by(
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
                    diffs.append((user, user_bal - change))
                    debt = min(debt + user_bal, 0)
                if debt < 0:
                    tup = diffs[0]
                    diffs[0] = (tup[0], tup[1] - debt)

                # formatting stuff
                max_name_len = max(len(item[0].name) for item in diffs)

                if namespace["accept"]:
                    for diff in diffs:
                        user = diff[0]
                        user_diff = diff[1]
                        user_bal = user.user_total
                        session.execute(
                            update(Participant).where(Participant.pid == user.pid)
                            .values(user_total=user_bal - user_diff)
                        )
                        cut = Cuts(pid=user.pid, cut=-user_diff, name="payout from " + str(cur_user.pid))
                        session.add(cut)

                    cut = Cuts(pid=cur_user.pid, cut=--cur_user.user_total, name="payout")
                    session.add(cut)
                    session.execute(
                        update(Participant).where(Participant.pid == cur_user.pid)
                        .values(user_total=0)
                    )
                    session.commit()
                    return order, f"{name.title()} pays to =>\n" + "\n".join(
                        f"{item[0].name.title():<{max_name_len}}: {cent_to_euro(item[1])}" for item in diffs)

                return order, f"possible transactions:\n{name.title()} pay => \n" + "\n".join(
                    f"{item[0].name.title():<{max_name_len}}: {cent_to_euro(item[1])}" for item in diffs)
        else:
            return order, "Nothing to payout"

    def reopen(*_) -> (Order, str):
        if order:
            return order, "Close current order first"
        else:
            opened_order = get_last_k_orders(session, 1, True)
            if opened_order:
                return opened_order[0], "Reopened order\n" + opened_order[0].print_order()
            else:
                return order, "No reopenable order"

    def history(namespace: Dict[str, Any]) -> (Order, str):
        orders = get_last_k_orders(session, namespace["k"], False)
        res = []
        for k, tempOrder in enumerate(orders):
            res.append(f"Order {k + 1}:\n" + tempOrder.print_order())
        return order, "\n------------------------------------------\n".join(res)

    def suggest(*_) -> (Order, str):
        last_orders = session.query(Cuts, Participant).filter(Participant.matrix_address == sender.lower()).filter(
            Cuts.pid == Participant.pid).filter(and_((Cuts.name != paid_string), (Cuts.name != "tip"))).order_by(
            Cuts.timestamp.desc()).limit(5).all()
        return order, f"As your last {len(last_orders)} order(s), you ordered: \n" + "\n".join(
            item[0].name + ", " + cent_to_euro(item[0].cut) for item in last_orders)

    def add_money(namespace: Dict[str, Any]) -> (Order, str):
        name = " ".join(namespace["name"]).lower()
        cur_user = find_match_in_database(name, session, True)
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
        all_balance = session.query(Participant.name, Participant.matrix_address, Participant.user_total).where(
            Participant.is_active.is_(True)).order_by(
            Participant.user_total.desc()).all()
        if not all_balance:
            return order, "no participants (yet)"
        max_name = max(len(user.name) for user in all_balance)
        max_address = max([len(user.matrix_address) for user in all_balance if user.matrix_address] + [len("None")])
        max_balance = max(len(str(user.user_total)) for user in all_balance) + 1
        msg = "Current balances: \n"
        msg = msg + "\n".join(
            [
                f"{user.name.title():<{max_name}} {'(' + user.matrix_address + ')' if user.matrix_address else 'None':>{max_address + 2}}): {cent_to_euro(user.user_total):>{max_balance}}"
                for user in all_balance])
        return order, msg

    def join(namespace: Dict[str, Any]) -> (Order, str):
        users = [user.matrix_address for user in session.query(Participant).all()]
        user_names = [user.name for user in session.query(Participant).all()]
        added_users = []
        logging.debug(f"users: {users}")
        logging.debug(f"user_names: {user_names}")
        if namespace["all"]:
            to_add = {k.lower(): v.lower() for k, v in members.items()}
        else:
            to_add = {sender: members[sender]}

        logging.debug(f"to_add with duplicates: {to_add}")

        duplicates_str = ""
        duplicates = [item for item, count in collections.Counter(to_add.values()).items() if count > 1]
        if duplicates:
            duplicates_str = ", ".join([dub.title() for dub in duplicates])
            to_add = {k: v for k, v in to_add.items() if v not in duplicates}


        logging.debug(f"to_add without duplicates: {to_add} - {duplicates_str}")

        for user in to_add:
            user = user.lower()
            logging.debug(f"adding user: {user}")
            # case 0: orderbot
            if "orderbot" in user.lower():
                logging.debug("orderbot")
                continue
            if user not in users and members[user].lower() not in user_names:
                # case 1: user name not yet taken, user matrix address not yet taken
                logging.debug(f"case 1: {user}")
                session.add(Participant(matrix_address=user.lower(), name=members[user].lower()))
                added_users.append(user)
            elif user not in users and members[user].lower() in user_names:
                # case 2: username already taken,
                taken_username = session.query(Participant).where(Participant.name == members[user].lower()).first()
                # case 2.1: user has not set a matrix address yet
                if taken_username.matrix_address is None:
                    logging.debug(f"case 2.1: {user}")
                    session.execute(
                        update(Participant).where(Participant.name == members[user].lower())
                        .values(matrix_address=user.lower())
                    )
                    added_users.append(user)
                # case 2.2: account was inactive
                elif not taken_username.is_active:
                    logging.debug(f"case 2.2: {user}")
                    session.execute(
                        update(Participant).where(Participant.name == members[user].lower())
                        .values(is_active=True, matrix_address=user.lower())
                    )
                    added_users.append(user)
                # case 2.3: user with taken username not in room anymore
                elif taken_username.matrix_address not in members:
                    logging.debug(f"case 2.3: {user}")
                    session.execute(
                        update(Participant).where(Participant.name == members[user].lower())
                        .values(matrix_address=user.lower())
                    )
                    added_users.append(user)
            elif user in users and members[user].lower() in user_names:
                # case 3: user name and matrix address already taken
                logging.debug(f"case 3: {user}")
                potential_user = session.query(Participant).where(
                    and_(Participant.name == members[user].lower(), Participant.matrix_address == user.lower())).first()
                if potential_user and not potential_user.is_active:
                    potential_user.is_active = True
                    added_users.append(user)
            else:
                # case 4: shrug
                logging.debug(f"case 4: {user}")
                pass
        session.commit()
        if not added_users:
            ret = "No new users added" + ("\nduplicate Usernames: " + duplicates_str if duplicates else "")
        else:
            logging.debug(f"added users: {added_users}")
            ret = "\n".join([f"added {user}:{members[user].title()}" for user in added_users]) + ("\nduplicate Usernames: " + duplicates_str if duplicates else "")
        return order, ret

    def register(namespace: Dict[str, Any]) -> (Order, str):
        name = " ".join(namespace["name"]).lower()
        address_user = session.query(Participant).where(
            Participant.name == name).first()
        if address_user and address_user.is_active:
            return order, "User already registered and active"
        elif address_user and address_user.is_active is False:
            session.execute(
                update(Participant).where(Participant.name == name)
                .values(is_active=True, matrix_address=None)
            )
            session.commit()
            return order, f"User {name.title()} reactivated"
        else:
            session.add(Participant(name=name))
            session.commit()
            return order, f"Added {name.title()}"

    def init(namespace: Dict[str, Any]) -> (Order, str):
        name = " ".join(namespace["name"]).lower()
        cur_user = find_match_in_database(name, session, True)
        if cur_user is None:
            return order, f"User {name.title()} not registered"
        bal = euro_to_cent(namespace["balance"])
        if cur_user.user_total == 0:
            session.add(
                Cuts(pid=cur_user.pid, cut=bal, name="initial balance")
            )
            cur_user.user_total = bal
            session.commit()
            return order, f"Set init balance for {cur_user.name.title()} to {cent_to_euro(bal)}"
        elif namespace["force"]:
            change = bal - cur_user.user_total
            cur_user.user_total = bal
            session.add(
                Cuts(pid=cur_user.pid, cut=change, name="initial balance")
            )
            session.commit()
            return order, f"Set balance for {cur_user.name.title()} to {cent_to_euro(bal)} -- by FORCE"
        else:
            return order, f"Balance of {cur_user.name.title()} is not zero, use 'balance' to check"

    def deinit(namespace: Dict[str, Any]) -> (Order, str):
        cur_user = None
        if namespace["self"]:
            cur_user = session.query(Participant).where(Participant.matrix_address == sender.lower()).first()
        else:
            name = " ".join(namespace["name"]).lower()
            if name:
                cur_user = find_match_in_database(name, session, True)

        if cur_user is None:
            return order, f"Could not exit: Either user not found or no user specified"
        elif cur_user.user_total != 0:
            return order, f"Balance of {cur_user.name.title()} is {cent_to_euro(cur_user.user_total)}"
        elif cur_user.user_total == 0:
            cur_user.is_active = False
            session.commit()
            return order, f"User {cur_user.name.title()} left..."

    def transfer(namespace: Dict[str, Any]) -> (Order, str):
        logging.debug(f"transfer: {namespace}")
        if namespace["origin"] is None:
            origin = sender.lower()
        else:
            origin = namespace["origin"].lower()
        if namespace["destination"] is None:
            return order, "No destination specified"

        origin_user = find_match_in_database(origin, session, True)
        destination_user = find_match_in_database(" ".join(namespace["destination"]).lower(), session, True)
        if origin_user is None:
            return order, f"User {origin.title()} not registered or inactive"
        if destination_user is None:
            return order, f"User {namespace['destination'].title()} not registered or inactive"
        if namespace["amount"]:
            amount = euro_to_cent(namespace["amount"])
        else:
            amount = origin_user.user_total
        origin_user.user_total += amount
        destination_user.user_total -= amount
        session.add(
            Cuts(pid=origin_user.pid, cut=amount, name="transfer to " + destination_user.name)
        )
        session.add(
            Cuts(pid=destination_user.pid, cut=-amount, name="transfer from " + origin_user.name)
        )
        session.commit()
        return order, f"Transferred {cent_to_euro(amount)} from {origin_user.name.title()} to {destination_user.name.title()}"

    main_parser = argparse.ArgumentParser(prog="OrderBot", add_help=False, usage="%(prog)s options:")
    main_subparser = main_parser.add_subparsers()

    order_parser = argparse.ArgumentParser(prog="UserBot", add_help=False, usage="%(prog)s options:")
    order_subparser = order_parser.add_subparsers()
    order_parser = main_subparser.add_parser("order", parents=[order_parser], help="manages orders")
    order_parser.add_argument("order", action="store_true", help="manages orders")

    user_parser = argparse.ArgumentParser(prog="UserBot", add_help=False, usage="%(prog)s options:")
    user_subparser = user_parser.add_subparsers()
    user_parser = main_subparser.add_parser("user", parents=[user_parser], help="manages users")
    user_parser.add_argument("user", action="store_true", help="manages users")

    start_parser = order_subparser.add_parser(cmd[4], help="start a new collective order")
    start_parser.set_defaults(func=start)
    start_parser.add_argument("name", nargs=argparse.ZERO_OR_MORE, default=["an", "unknown", "order"],
                              help="name of collective order")

    add_parser = order_subparser.add_parser(cmd[1], help="add item of a user to order")
    add_parser.set_defaults(func=add)
    add_parser.add_argument("order name", type=str, nargs=argparse.ZERO_OR_MORE, default=["unknown", "Meal"],
                            help="name of order")
    add_parser.add_argument("price", type=float, help="price of order")
    add_parser.add_argument("--name", "-n", type=str,
                            help="orderer, if different from messenger, in quotes")

    tip_parser = order_subparser.add_parser(cmd[3], help="set tip of the order")
    tip_parser.set_defaults(func=tip)
    tip_parser.add_argument("tip", type=float, help="tip amount")

    remove_parser = order_subparser.add_parser(cmd[2], help="remove a user's item from the current collective order, all items of a user or all users")
    remove_parser.set_defaults(func=remove)
    remove_parser.add_argument( "--ordername", "-o", type=str, nargs=argparse.ZERO_OR_MORE,
                               help="name of order, otherwise all are removed (see -a flag)", required=False)
    remove_parser.add_argument("--name", "-n", type=str, nargs= argparse.ONE_OR_MORE,
                               help="orderer, if different from messenger", required=False)
    remove_parser.add_argument("--all", "-a", action='store_true',
                               help="all orders are removed")

    end_parser = order_subparser.add_parser(cmd[6], help="finish collective order")
    end_parser.set_defaults(func=pay)
    end_parser.add_argument("--name", "-n", type=str, nargs=argparse.ONE_OR_MORE,
                            help="payer, if different from messenger")
    end_parser.add_argument("--amount", "-a", type=float,
                            help="amount paid, if not specified, everything is paid, and the order is finished")

    cancel_parser = order_subparser.add_parser(cmd[5], help="cancel current collective order")
    cancel_parser.set_defaults(func=cancel)

    print_parser = order_subparser.add_parser(cmd[7], help="display current collective order")
    print_parser.set_defaults(func=print_order)
    print_parser.add_argument("--self", "-s", action='store_true', help="displays only the orders of the messenger")

    reopen_parser = order_subparser.add_parser(cmd[13], help="reopen last order, if no current order")
    reopen_parser.set_defaults(func=reopen)

    suggest_parser = order_subparser.add_parser(cmd[14],
                                                help="return the last 5 ordered item of the user, with pricing")
    suggest_parser.set_defaults(func=suggest)

    reorder_parser = order_subparser.add_parser(cmd[18], help="reorder the last item of a user, from the last order")
    reorder_parser.set_defaults(func=reorder)
    reorder_parser.add_argument("--name", "-n", type=str, nargs=argparse.ONE_OR_MORE)

    history_parser = order_subparser.add_parser(cmd[19], help="display history of the last [k] orders")
    history_parser.set_defaults(func=history)
    history_parser.add_argument("--k", "-k", type=int, default=5, help="number of orders to display")

    edit_parser = order_subparser.add_parser(cmd[12], help="edit the price of an item")
    edit_parser.set_defaults(func=edit)
    edit_parser.add_argument("order name", type=str, nargs=argparse.ONE_OR_MORE, help="name of order")
    edit_parser.add_argument("new price", type=float, help="new price")
    edit_parser.add_argument("--name", "-n", type=str,
                             help="orderer, if different from messenger")

    register_parser = user_subparser.add_parser(cmd[0],
                                                help="register a different user, e.g. via just the name, use join to register yourself")
    register_parser.set_defaults(func=register)
    register_parser.add_argument("name", nargs=argparse.ONE_OR_MORE, type=str)

    pay_parser = user_subparser.add_parser(cmd[17], help="transfer money from one user to another")
    pay_parser.set_defaults(func=transfer)
    pay_parser.add_argument("amount", type=float, help="Amount to be transferred")
    pay_parser.add_argument("--origin", "-o", type=str, help="source")
    pay_parser.add_argument("destination", type=str, nargs=argparse.ONE_OR_MORE, help="destination")

    payout_parser = user_subparser.add_parser(cmd[8], help="get a suggestion for a potential payout")
    payout_parser.set_defaults(func=payout)
    payout_parser.add_argument("--name", "-n", type=str, nargs=argparse.ONE_OR_MORE,
                               help="orderer, if different from messenger")
    payout_parser.add_argument("--accept", "-a", action='store_true',
                               help="accepts the payout, check payout command without this flag first, if unnsure\nIf suggestion is not accepted, use 'transfer' to manually balance the debt/due.")

    if loglevel == logging.DEBUG:
        add_money_parser = user_subparser.add_parser(cmd[9], help="add initial balance to a user", prefix_chars="@")
        add_money_parser.set_defaults(func=add_money)
        add_money_parser.add_argument("name", nargs=argparse.ONE_OR_MORE, type=str, help="recipient")
        add_money_parser.add_argument("balance", type=float, help="balance")

    balance_parser = user_subparser.add_parser(cmd[10], help="display the balance of all users")
    balance_parser.set_defaults(func=balance)

    join_parser = user_subparser.add_parser(cmd[11], help="join system with matrix-address")
    join_parser.add_argument("--all", "-a", action='store_true', help="adds all current members of the room to the db")
    join_parser.set_defaults(func=join)

    init_parser = user_subparser.add_parser(cmd[15], help="initialize a user's balance")
    init_parser.set_defaults(func=init)
    init_parser.add_argument("name", nargs=argparse.ONE_OR_MORE, type=str, help="name of user")
    init_parser.add_argument("balance", type=float, help="balance")
    init_parser.add_argument("--force", "-f", action='store_true', help="force initialization, even if balance is not zero")

    deinit_parser = user_subparser.add_parser(cmd[16], help="deactivates user, if balance is zero")
    deinit_parser.set_defaults(func=deinit)
    deinit_parser.add_argument("--self", "-s", action='store_true', help="deinitializes messenger")
    deinit_parser.add_argument("name", nargs=argparse.ZERO_OR_MORE, type=str, help="name of user")

    try:
        args = main_parser.parse_args(inp)
        logging.debug(args)
        result = args.func(vars(args))
        return result

    # eror handling for wrong input or help command
    except (SystemExit, AttributeError, argparse.ArgumentError):
        traceback.print_exc()
        if inp[0] in ["order", "user"]:
            if len(inp) > 1 and inp[1] in cmd and inp[0] == "order":
                possible_parsers = [action for action in order_parser._actions if
                                    isinstance(action, argparse._SubParsersAction)]
                for parser_action in possible_parsers:
                    for choice, subparser in parser_action.choices.items():
                        if choice == inp[1]:
                            return order, subparser.format_help()
                return order, order_parser.format_help()
            elif len(inp) > 1 and inp[1] in cmd and inp[0] == "user":
                possible_parsers = [action for action in user_parser._actions if
                                    isinstance(action, argparse._SubParsersAction)]
                for parser_action in possible_parsers:
                    for choice, subparser in parser_action.choices.items():
                        if choice == inp[1]:
                            return order, subparser.format_help()
                return order, user_parser.format_help()

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
        return order, "Database error, please try again later."

    except Exception as e:
        logging.error(e)
        traceback.print_exc()
        return order, "Unknown error, please try again later."
