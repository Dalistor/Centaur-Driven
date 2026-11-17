from .pricing import calc


def receipt(orders):
    """Uma linha por pedido; `calc` decide o valor de cada um."""
    return [f'{name}: {calc(items, coupon):.2f}' for name, items, coupon in orders]
