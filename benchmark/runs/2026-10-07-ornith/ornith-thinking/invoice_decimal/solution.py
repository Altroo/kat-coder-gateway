```python
from decimal import Decimal, ROUND_HALF_UP, InvalidOperation, localcontext


def _round_cents(value):
    return value.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def _parse_decimal(value, name):
    try:
        result = Decimal(value)
    except (InvalidOperation, TypeError, ValueError):
        raise ValueError(f"{name} is not a valid decimal: {value!r}")
    if not result.is_finite():
        raise ValueError(f"{name} is not finite: {value!r}")
    return result


def invoice_total(lines, discount_percent="0"):
    discount = _parse_decimal(discount_percent, "discount_percent")
    if discount < 0 or discount > 100:
        raise ValueError(
            f"discount_percent out of range 0..100: {discount_percent!r}"
        )

    if not lines:
        return {"net": "0.00", "tax": "0.00", "total": "0.00"}

    one_hundred = Decimal(100)
    total_net = Decimal(0)
    total_tax = Decimal(0)

    with localcontext() as ctx:
        ctx.prec = 50
        for line in lines:
            if not isinstance(line, dict):
                raise ValueError(
                    f"each line must be a dict, got {type(line).__name__}"
                )
            for field in ("quantity", "unit_price", "vat_percent"):
                if field not in line or line[field] is None