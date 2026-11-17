import unittest

import shop
from shop.report import receipt


class ShopTests(unittest.TestCase):
    def test_total_and_receipt(self):
        total = getattr(shop, 'order_total', None) or shop.calc
        self.assertEqual(total([(10, 2), (5, 1)], 'VIP'), 22.5)
        self.assertEqual(receipt([('ana', [(10, 1)], None)]), ['ana: 10.00'])


if __name__ == '__main__':
    unittest.main()
