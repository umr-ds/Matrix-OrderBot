import config
from order import Order


def parse_input(input, connection, cursor, order):
    key_word = input[0]
    cmd = config.commands
    msg = "empty string"
    if key_word in cmd[4]:      #start
        return True, Order(), "Started Transaction"
    if key_word in cmd[5]:      #abort
        return True, None, "Aborted Transaction"
    if key_word in cmd[6]:      #commit order
        if len(input) > 1:
            commit_order(input, connection, cursor, order )
            return True, None, order.to_string()
    if key_word in cmd[0]:      # add user
        username, servername = add_user(cursor, connection, input)
        return False, order, f"added User: {username},{servername}"
    if order is None:
        return False, order, "No order active atm, user Start"
    if key_word in cmd[1]:
        msg = add_order(cursor, connection, input, order)
    if key_word in cmd[2]:
        remove_pos_from_order(input, order)
        msg = "removed pos (debug, change later)"
    if key_word in cmd[3]:
        add_tip(input, order)
        msg = "added tip (debug, change later)"
    return False, order, msg


def add_user(cursor, conn, input):
    if len(input) < 2:
        return "No", "User (Debug)"
    cursor.execute("SELECT name from participant")
    all_user = cursor.fetchall()
    print(all_user)
    if all_user is not None and input[1] in all_user:
        cursor.execute("SELECT * from participant where name = %s", input[1])
        print(cursor.fetchall())
    else:
        cursor.execute("INSERT INTO participant(NAME, USERNAME) values (%s, %s)", (input[1], input[1] + "@Homeserver"))
        conn.commit()
    return input[1], input[1] + "@Homeserver"


def add_order(cursor, connection, input, order):
    if len(input) < 3 or not is_number(input[2]) or float(input[2]) < 0:
        return
    cursor.execute("SELECT name from participant")
    all_user = [x[0] for x in cursor.fetchall()]
    if input[1] not in all_user:
        add_user(cursor, connection, input[0:2])
    order.add_pos(input[1], float(input[2]))
    return f"Order added for {input[1]} with {input[2]}"


def add_tip(input, order):
    if len(input) != 2 or not is_number(input[1]) or float(input[1]) < 0:
        return
    order.add_tip(float(input[1]))


def remove_pos_from_order(input, order):
    if len(input) < 2:
        return
    order.remove(input[1])


def commit_order(inp, conn, cur, order):
    if len(inp) != 2:
        return False

    order.pay(inp[1])

    order, price, tip = order.return_data()
    cur.execute("SELECT nextval(pg_get_serial_sequence('orders', 'order_id'))")
    cut_id = cur.fetchone()[0]
    cur.execute("INSERT INTO orders(ordeR_id, total, price, tip, timestp) values (%s, %s, %s, %s, now())",
                (cut_id, price + tip, price, tip))
    conn.commit()
    for x in order.keys():
        cur.execute("""SELECT id from participant where name = %s""", (x,))
        user_id = cur.fetchone()[0]
        cur.execute("INSERT INTO cuts(order_id, id, cut, timestp) values (%s, %s, %s, now())",
                    (cut_id, user_id, order[x] + tip/len(order.keys()) ))
        conn.commit()
        cur.execute("UPDATE participant SET user_total = user_total + %s where id = %s", (order[x] + tip/len(order.keys()), user_id))
        conn.commit()

    return True


def is_number(s):
    try:
        float(s)
        return True
    except ValueError:
        return False
