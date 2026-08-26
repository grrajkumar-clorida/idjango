from types import SimpleNamespace

from django.test import TestCase

from data.strategies.ma50_strategy import MA50Strategy


class MA50TargetStatusTestCase(TestCase):
    def setUp(self):
        self.strategy = MA50Strategy()
        self.stock = SimpleNamespace(status=8, stock_cmp=100.0)

    def _live(self, price):
        return SimpleNamespace(close_price=price)

    def test_target_bands_from_entry(self):
        cases = (
            (107.0, 9),   # placed fill, below 8% → Target 1
            (108.0, 9),   # +8% Target 1
            (110.0, 10),  # +10% Target 2
            (115.0, 11),  # +15% Target 3
            (120.0, 12),  # +20% Above T3
            (125.0, 13),  # +25% Altra
        )
        for price, expected in cases:
            self.stock.status = 8
            got = self.strategy.update_status_based_on_price(
                self.stock, self._live(price), 100.0
            )
            self.assertEqual(got, expected, f"price {price} expected {expected} got {got}")

    def test_does_not_drop_after_target(self):
        self.stock.status = 11
        got = self.strategy.update_status_based_on_price(
            self.stock, self._live(105.0), 100.0
        )
        self.assertEqual(got, 11)

    def test_skygold_and_ashokley_from_desk(self):
        # ASHOKLEY ~12.89% → Target 2
        self.stock.status = 8
        self.assertEqual(
            self.strategy.update_status_based_on_price(
                self.stock, self._live(177.47), 157.20
            ),
            10,
        )
        # JYOTHYLAB ~1.42% placed fill → Target 1
        self.stock.status = 8
        self.assertEqual(
            self.strategy.update_status_based_on_price(
                self.stock, self._live(210.1), 207.15
            ),
            9,
        )
        # SKYGOLD ~27.26% → Altra
        self.stock.status = 8
        self.assertEqual(
            self.strategy.update_status_based_on_price(
                self.stock, self._live(853.5), 670.70
            ),
            13,
        )
