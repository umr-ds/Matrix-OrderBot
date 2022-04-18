class Order:

    def __init__(self):
        self.order = {}
        self.price = 0
        self.tip = 0
        self.paid = True

    def add_pos(self, user, amount):
        if user in self.order:
            self.order[user] = self.order[user] + amount
        else:
            self.order[user] = amount
        self.price = self.price + amount
        print(self.return_data())
        self.paid = False

    def remove(self, user):
        if user not in self.order:
            print(user, "not in order")
        else:
            self.price = self.price - self.order[user]
            del self.order[user]
        print(self.return_data())

    def add_tip(self, tip):
        if tip >= 0:
            self.tip = self.tip + tip

    def remove_tip(self):
        self.tip = 0

    def return_data(self):
        return self.order, self.price, self.tip

    def pay(self, user):
        if user not in self.order:
            self.order[user] = 0
        self.order[user] = self.order[user] - (self.price + self.tip)
        self.paid = True
