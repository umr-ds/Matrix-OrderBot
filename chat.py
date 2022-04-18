from psycopg2 import Error, connect
from config import config
from order import Order
from order_parser import parse_input, commit_order
from setup import setup

if __name__ == '__main__':
    conn = None
    order = None
    try:
        conn = connect(**config('postgresql'))
        cur = conn.cursor()
        print("New Setup?")
        if input() == "y":
            setup(conn, cur)
        while 1:
            inp = input().split()
            key_word = inp[0].lower()
            if key_word == "exit":
                cur.close()
                conn.close()
                break
            elif key_word == "start":
                order = Order()
            elif key_word == "abort":
                order = None
            elif key_word == "end" and order is not None and len(inp) == 2:
                if commit_order(inp, conn, cur, order):
                    order = None
            elif order is not None:
                parse_input(inp, conn, cur, order)
            print(inp)

    except (Exception, Error) as error:
        print("Connection error")
        print(error)
    finally:
        if conn:
            cur.close()
            conn.close()
