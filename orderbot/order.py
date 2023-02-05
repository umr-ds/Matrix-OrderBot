import logging
from typing import Tuple, List, Dict

from orderbot.db_classes import DB_Order

order_version: int = 1


class Order:

    def __init__(self, name="Order"):
        self.order: dict[str, List[Tuple[str, int]]] = {}
        self.name: str = name
        self.price: int = 0
        self.tip: int = 0
        self.paid: bool = False
        self.recommended_payer: Tuple[str, int] = None
        self.version: int = 1
        self.payers: Dict[str, int] = {}

    def __str__(self):
        return self.print_order()

    def print_order(self, user: str = None) -> str:
        import orderbot.util
        title = f"{self.name}"
        if len(self.order) > 0:
            maxName = max([len(user) for user in self.order])
            maxItem = max([len(item[0]) for user in self.order for item in self.order[user]])
            maxAmount = len(str(self.price + self.tip)) + 1
        else:
            return "empty order"

        order = ""
        for user in self.order:
            order += f"{user.title():<{maxName}}: "
            count = 0
            for item in self.order[user]:
                if item[0] == "paid amount":
                    continue
                if count == 0:
                    order += f"{item[0]:<{maxItem}} {orderbot.util.cent_to_euro(item[1]):>{maxAmount}}"
                    count += 1
                else:
                    order += f"{'':<{maxName + 2}}{item[0]:<{maxItem}} {orderbot.util.cent_to_euro(item[1]):>{maxAmount}}"
                order += "\n"

        recommadation = f"(Recommended Payer: {self.recommended_payer[0].title() if self.recommended_payer else 'None'} [{self.recommended_payer[1] if self.recommended_payer else '0'}])"
        if self.paid is True:
            paid_string = f"Paid by {', '.join([f'{user.title()} [{orderbot.util.cent_to_euro(self.payers[user])}]' for user in self.payers])}"
        elif self.paid is False and len(self.payers) > 0:
            paid_string = f"Partially paid by {', '.join([f'{user.title()} [{orderbot.util.cent_to_euro(self.payers[user])}]' for user in self.payers])}"
            paid_string += f" (Missing {orderbot.util.cent_to_euro(self.price + self.tip - self.sum_payed())})"
        else:
            paid_string = "Not paid yet"

        s = (title, order,
             f"{'Tip:':<{maxName + 2}}{'':<{maxItem}} {orderbot.util.cent_to_euro(self.tip):>{maxAmount}}",
             f"{'Total:':<{maxName + 2}}{'':<{maxItem}} {orderbot.util.cent_to_euro(self.price):>{maxAmount}}",
             f"{'Sum:':<{maxName + 2}}{'':<{maxItem}} {orderbot.util.cent_to_euro((self.tip + self.price)):>{maxAmount}}",
             recommadation,
             paid_string)

        return "\n".join(s)


    def add_pos(self, user: str, item: str, amount: int) -> None:
        if user in self.order:
            self.order[user].append((item, amount))
        else:
            self.order[user] = [(item, amount)]
        self.price = self.price + amount
        self.paid = False


    def remove(self, user: str, item: str = None) -> None:
        if user.lower() not in self.order:
            pass
        elif item is None:
            for entry in self.order[user]:
                self.price = self.price - entry[1]
            del self.order[user]

        else:
            for c, entry in enumerate(self.order[user]):
                if entry[0].lower() == item.lower():
                    self.price = self.price - entry[1]
                    self.order[user].remove(entry)
            if len(self.order[user]) == 0:
                del self.order[user]
        logging.debug(self.price + self.paid)
        if self.price <= sum(self.payers.values()):
            self.paid = True


    def add_tip(self, tip: int) -> None:
        if tip >= 0:
            self.tip = self.tip + tip


    def remove_tip(self):
        self.tip = 0


    def sum_order(self, user: str) -> int:
        if user in self.order:
            return sum([item[0] for item in self.order[user]])


    def pay(self, user: str, amount: int = None) -> None:
        if user not in self.order:
            self.order[user] = []
        if amount is None:
            self.payers[user] = self.price + self.tip - self.sum_payed() + self.payers[user] if user in self.payers else self.price + self.tip - self.sum_payed()
            self.paid = True
        else:
            already_paid = self.payers[user] if user in self.payers else 0
            remaining = self.price + self.tip - self.sum_payed()
            if amount - already_paid >= remaining:
                self.payers[user] = amount
                self.paid = True
                self.tip = self.sum_payed() - self.price
            else:
                self.payers[user] = amount
                self.paid = False


    def to_dborder(self) -> DB_Order:
        return DB_Order(name=self.name, total=self.price + self.tip, price=self.price,
                        tip=self.tip)


    def set_recommended_payer(self, user: str, amount: int) -> None:
        self.recommended_payer = (user, amount)

    def sum_payed(self) -> int:
        return sum(self.payers.values())

    def set_tip(self, ttip):
        if ttip >= 0:
            self.tip = ttip

    def remove_all(self):
        self.order = {}
        self.price = 0
        self.paid = False
        self.recommended_payer = None

    def edit_pos(self, user: str, item: str, amount: int) -> None:
        if user in self.order:
            for c, entry in enumerate(self.order[user]):
                if entry[0].lower() == item.lower():
                    self.price = self.price - entry[1] + amount
                    self.order[user][c] = (entry[0], amount)
                    return True
        return False