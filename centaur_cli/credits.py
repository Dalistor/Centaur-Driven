"""Valores e apresentação dos créditos consultados no OpenRouter."""

from dataclasses import dataclass
from decimal import Decimal


def amount(value):
    number = Decimal(str(value))
    if not number.is_finite() or number < 0:
        raise ValueError('Valor de crédito inválido.')
    return number


@dataclass(frozen=True)
class CreditBalance:
    scope: str
    total: Decimal | None
    remaining: Decimal | None

    @property
    def fraction(self):
        if self.total is None or self.remaining is None:
            return None
        return min(Decimal(1), self.remaining / self.total) if self.total else Decimal(0)


def credit_label(balance, status, width):
    if status == 'setup':
        return 'Créditos: configure o backend', 'muted'
    if status == 'unsupported':
        return 'Créditos: consulte o cliente conectado', 'muted'
    cells = 10 if width >= 65 else 5
    if balance is None:
        message = 'consultando' if status == 'loading' else 'indisponível'
        return f'Créditos [{"·" * cells}] {message}', 'muted'
    scope = ('Saldo conta' if width >= 65 else 'Conta') if balance.scope == 'account' else 'Limite chave'
    if balance.remaining is None:
        suffix = ' · conta indisponível' if width >= 65 else ''
        return f'{scope} [{"·" * cells}] sem limite{suffix}', 'muted'
    fraction = balance.fraction
    filled = round(fraction * cells)
    bar = '█' * filled + '░' * (cells - filled)
    stale = '~' if status == 'error' else ''
    style = 'warning' if fraction <= Decimal('0.2') or stale else 'green'
    return f'{scope} [{bar}] {stale}US$ {balance.remaining:.2f}', style
