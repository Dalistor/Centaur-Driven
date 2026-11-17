"""Preço final de um pedido."""

DISCOUNTS = {'VIP': 0.10, 'STAFF': 0.25}


def calc(items, coupon=None):
    """Soma preço × quantidade e aplica o desconto do cupom, se houver."""
    subtotal = sum(price * quantity for price, quantity in items)
    return round(subtotal * (1 - DISCOUNTS.get(coupon, 0)), 2)
