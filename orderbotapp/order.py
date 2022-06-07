class Order:

    def __init__(self, name="Order"):
        self.order = {}
        self.name = name
        self.price = 0
        self.tip = 0
        self.paid = True

    def __str__(self):
        s = (
            f"{self.name}",
            "\n".join([
                f"{person}:\t {', '.join([' : '.join([item[0], str(item[1])]) for item in betrag if item[0] != 'paid amount'])}"
                for person, betrag in self.order.items() if not (len(betrag) == 1 and betrag[0][0] == 'paid amount')]),
            f"Tip:\t {str(self.tip)}",
            f"Total:\t {str(self.price)}",
            f"Sum:\t {str(self.tip + self.price)}",
            f"Paid by: {self.paid}"
        )
        return "\n".join(s)

    def add_pos(self, user, item, amount):
        if user in self.order:
            self.order[user].append((item, amount))
        else:
            self.order[user] = [(item, amount)]
        self.price = self.price + amount
        self.paid = None

    def remove(self, user, item=None):
        if user not in self.order:
            pass
        elif user is None:
            for entry in self.order[user]:
                self.price = self.price - entry[1]
            del self.order[user]
        else:
            for c, entry in enumerate(self.order[user]):
                if entry[0] == item:
                    self.price = self.price - entry[1]
                    self.order[user].remove(c)

    def add_tip(self, tip):
        if tip >= 0:
            self.tip = self.tip + tip

    def remove_tip(self):
        self.tip = 0

    def sum_order(self, user):
        if user in self.order:
            return sum([item[0] for item in self.order[user]])

    def pay(self, user, amount=None):
        if user not in self.order:
            self.order[user] = []
        if amount is None:
            self.order[user].append(("paid amount", -(self.price + self.tip)))
            self.paid = user
        else:
            self.order[user].append(("paid amount", -amount))
