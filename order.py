# It's a class that represents an order
class Order:

    def __init__(self, name="Order"):
        self.order = {}
        self.name = name
        # todo: also save name, and individual price of each item
        self.price = 0
        self.tip = 0
        self.paid = True

    def __str__(self):
        """
        It takes a dictionary of dictionaries and returns a string
        :return: A string
        """
        s = (
            f"{self.name}",
            "\n".join([
                f"{person}:\t {', '.join([' : '.join([item[0], str(item[1])]) for item in betrag if item[0] != 'Payout (debug)'])}"
                for person, betrag in self.order.items()]),
            f"Tip:\t {str(self.tip)}",
            f"Total:\t {str(self.price)}",
            f"Sum:\t {str(self.tip + self.price)}",
            f"Paid by: {self.paid}"
        )
        # todo: Price per Person, Share per Person, Tip
        return "\n".join(s)

    def add_pos(self, user, item, amount):
        """
        It adds an item to the order, and then prints the order

        :param user: The user who is ordering
        :param item: the item that the user is buying
        :param amount: The amount of money the user is paying
        """
        if user in self.order:
            self.order[user].append((item, amount))
        else:
            self.order[user] = [(item, amount)]
        self.price = self.price + amount
        print(self.return_data())
        self.paid = None

    def remove(self, user):
        """
        It removes a user from the order dictionary and subtracts the price of the items they ordered
        from the total price

        :param user: the user who is ordering
        """
        if user not in self.order:
            print(user, "not in order")
        else:
            for item in self.order[user]:
                self.price = self.price - item[1]
            del self.order[user]
        print(self.return_data())

    def add_tip(self, tip):
        """
        **add_tip** takes in a parameter **self** and **tip**, and adds the tip to the tip attribute of the object

        :param tip: the tip amount
        """
        if tip >= 0:
            self.tip = self.tip + tip

    def remove_tip(self):
        """
        **remove_tip**: This function removes the tip from the total bill
        """
        self.tip = 0

    def return_data(self):
        """
        The function return_data() returns the order, price, and tip of the object
        :return: The order, price, and tip are being returned.
        """
        return self.order, self.price, self.tip

    def sum_order(self, user):
        """
        It returns the sum of the first item in each tuple in the order dictionary.

        :param user: The user who's order we want to sum up
        :return: The sum of the prices of the items in the order.
        """
        if user in self.order:
            return sum([item[0] for item in self.order[user]])

    def pay(self, user):
        """
        It adds a tuple to the order dictionary, with the first element being a string and the second element being the
        negative of the price plus the tip

        :param user: The user who is paying
        """
        self.order[user].append(("Payout (debug)", -(self.price + self.tip)))
        self.paid = user
