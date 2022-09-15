from typing import Union, Tuple, List

import order_parser
from db_classes import DB_Order


class Order:

    def __init__(self, name="Order"):
        self.order: dict[str, List[Tuple[str, int]]] = {}
        self.name: str = name
        self.price: int = 0
        self.tip: int = 0
        self.paid: Union[str, bool] = True

    def __str__(self):
        return self.print_order()

    def print_order(self, user: str = None) -> str:
        s = (
            f"{self.name}",
            "\n".join([
                f"{person}:\t {', '.join([' : '.join([item[0], order_parser.cent_to_euro(item[1])]) for item in betrag if item[0] != 'paid amount'])}"
                for person, betrag in self.order.items() if
                not (len(betrag) == 1 and betrag[0][0] == 'paid amount') and user is None or person == user]),
            f"Tip:\t {order_parser.cent_to_euro(self.tip)}",
            f"Total:\t {order_parser.cent_to_euro(self.price)}",
            f"Sum:\t {order_parser.cent_to_euro((self.tip + self.price))}",
            f"Paid by: {self.paid}"
        )
        return "\n".join(s)

    def add_pos(self, user: str, item: str, amount: int) -> None:
        if user in self.order:
            self.order[user].append((item, amount))
        else:
            self.order[user] = [(item, amount)]
        self.price = self.price + amount
        self.paid = None

    def remove(self, user: str, item: str = None) -> None:
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
            self.order[user].append(("paid amount", -(self.price + self.tip)))
            self.paid = user
        else:
            self.order[user].append(("paid amount", -amount))

    def to_dborder(self) -> DB_Order:
        return DB_Order(name=self.name, total=self.price + self.tip, price=self.price,
                        tip=self.tip)
