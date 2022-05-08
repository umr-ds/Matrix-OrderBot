def setup(connection, cursor):
    cursor.execute("DROP TABLE IF EXISTS cuts")
    cursor.execute("DROP TABLE IF EXISTS orders")
    cursor.execute("DROP TABLE IF EXISTS participant")
    connection.commit()
    cursor.execute('''CREATE TABLE participant
            (
            id SERIAL PRIMARY KEY,
            name VARCHAR NOT NULL, 
            username VARCHAR, 
            user_total NUMERIC DEFAULT 0
            )''')
    cursor.execute('''CREATE TABLE orders
            (
            order_id SERIAL PRIMARY KEY,
            total NUMERIC CHECK (total >= 0),
            price NUMERIC CHECK (price >= 0),
            tip NUMERIC CHECK (tip >= 0),
            timestp date,
            CHECK (total = price + tip)
            )''')
    cursor.execute('''CREATE TABLE cuts
            (
            order_id INT REFERENCES orders(order_id), 
            id INT REFERENCES participant(id),
            cut NUMERIC NOT NULL,
            timestp date
            )''')
    connection.commit()
