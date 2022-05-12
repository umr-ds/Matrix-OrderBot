import re

import config
from order import Order

cmd = config.commands


def parse_input(inp, connection, cursor, order, sender):
    """
    It takes in a string, a connection to the database, a cursor, and an order object. It then parses the string and
    returns a boolean, an order object, and a string

    :param sender:
    :param inp: the input string
    :param connection: the connection to the database
    :param cursor: the cursor object. The object you use to execute queries
    :param order: the order object
    :return: The return value is a tuple of three values.
    The first value is a boolean, which is True if the order is finished and False if it is not.
    The second value is the order object, which is None if the order is finished.
    The third value is a string, which is the message to be displayed to the user.
    """
    key_word = inp[0].lower()
    msg = "empty string"
    print(key_word, key_word in cmd[0], cmd[0])
    if key_word in cmd[8] and order is not None:
        return False, order, str(order)
    if key_word in cmd[4]:  # start
        if len(inp) == 1:
            return True, Order(), "Started Transaction"
        else:
            order = Order(" ".join(inp[1:]))
            return True, order, f"Started Order {order.name}"
    elif key_word in cmd[7]:  # help
        return False, order, str(cmd)
    elif key_word in cmd[5]:  # abort
        return True, None, "Aborted Transaction"
    elif key_word in cmd[6]:  # commit order
        if order is not None:
            commit_order(inp, connection, cursor, order, sender)
            return True, None, str(order)
        else:
            # TODO: Keep message?
            return False, None, "No order to end (debug)"
    elif key_word in cmd[0]:  # add user
        print("hi")
        username, servername, added = add_user(cursor, connection, inp, sender)
        if not added:
            return False, order, f"added User: {username},{servername}"
        else:
            return False, order, f"User already in System: {username},{servername}"
    elif order is None:
        return False, order, "No order active atm, use 'start' "
    elif key_word in cmd[1]:
        msg = add_order(cursor, connection, inp, order, sender)
    elif key_word in cmd[2]:
        remove_pos_from_order(inp, order, sender)
        msg = "removed pos (debug, change later)"
    elif key_word in cmd[3]:
        add_tip(inp, order)
        msg = "added tip (debug, change later)"
    return False, order, msg


def add_user(cursor, conn, inp, sender):
    """
    It takes in a cursor, a connection, and a list of strings. It then checks if the list is empty, and if it is, it
    returns a string. If it isn't, it checks if the second element of the list is in a list of strings, and if it is,
    it returns a string. If it isn't, it inserts the second element of the list into a table, and then returns a string

    :param sender:
    :param cursor: The cursor object
    :param conn: The connection to the database
    :param inp: a list of strings, the first element is the command, the rest are the arguments
    :return: The name and username of the user being added.
    """
    username = ""
    if len(inp) == 2:
        username = inp[1]
        sender = ""
    else:
        username = re.search('@(.+?):.?', sender).group(1)
    cursor.execute("SELECT name, username from participant")
    all_user = [item for sublist in cursor.fetchall() for item in sublist]
    print("all users:", list(all_user))
    if all_user is not None and sender in list(all_user):
        cursor.execute("SELECT * from participant where name = %s or username = %s", (username, sender))
        print(cursor.fetchall())
        return username, sender, True
    else:
        cursor.execute("INSERT INTO participant(NAME, USERNAME) values (%s, %s)", (username, sender))
        conn.commit()
        return username, sender, False


def add_order(cursor, connection, inp, order, sender):
    """
    It adds an order to the order object

    :param sender:
    :param cursor: the cursor object
    :param connection: the connection to the database
    :param inp: a list of strings, the first element is the command, the second is the user, the third is the number of
    pizzas
    :param order: the order object
    :return: A string with the name of the user and the amount of pizza they ordered.
    """
    """
    It adds an order to the order object

    :param cursor: the cursor object
    :param connection: the connection to the database
    :param inp: a list of strings, the first element is the command, the second is the user, the third is the number 
    of pizzas
    :param order: the order object
    :return: A string with the name of the user and the amount of pizza they ordered.
    """
    if len(inp) == 3 and is_number(inp[2]):
        print(sender)
        cursor.execute("SELECT username from participant where username = %s", (sender,))
        all_user = [x[0] for x in cursor.fetchall()]

        if not all_user:
            add_user(cursor, connection, inp, sender)
        order.add_pos(sender, inp[1], float(inp[2]))
        return f"Order {inp[1]} added for {sender} with {inp[2]}€"
    return

def add_tip(inp, order):
    if len(inp) != 2 or not is_number(inp[1]) or float(inp[1]) < 0:
        return
    order.add_tip(float(inp[1]))


def remove_pos_from_order(inp, order, sender):
    if len(inp) < 2:
        return
    order.remove(inp[1])


def commit_order(inp, conn, cur, order, sender):
    print(sender)
    order.pay(sender)

    order, price, tip = order.return_data()
    cur.execute("SELECT nextval(pg_get_serial_sequence('orders', 'order_id'))")
    cut_id = cur.fetchone()[0]
    cur.execute("INSERT INTO orders(order_id, total, price, tip, timestp) values (%s, %s, %s, %s, now())",
                (cut_id, price + tip, price, tip))
    conn.commit()
    for x in order.keys():
        cur.execute("""SELECT id from participant where username = %s""", (x,))
        user_id = cur.fetchone()[0]
        print(order[x], tip)
        cur.execute("INSERT INTO cuts(order_id, id, cut, timestp) values (%s, %s, %s, now())",
                    (cut_id, user_id, sum(item[1] for item in order[x]) + tip / len(order.keys())))
        conn.commit()
        cur.execute("UPDATE participant SET user_total = user_total + %s where id = %s",
                    (sum(item[1] for item in order[x]) + tip / len(order.keys()), user_id))
        conn.commit()

    return True


def is_number(s):
    try:
        float(s)
        return True
    except ValueError:
        return False
