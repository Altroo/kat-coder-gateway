from decimal import Decimal, ROUND_HALF_UP, InvalidOperation


def invoice_total(lines, discount_percent="0"):
    try:
        discount = Decimal(discount_percent)
    except (InvalidOperation, ValueError, ArithmeticError):
        raise ValueError("Invalid discount_percent")

    if not discount.is_finite():
        raise ValueError("Non-finite discount_percent")
    if discount < 0 or discount > 100:
        raise ValueError("Discount out of range")

    if not isinstance(lines, list):
        raise ValueError("lines must be a list")

    two_places = Decimal('0.01')
    hundred = Decimal('100')

    total_net = Decimal('0')
    total_tax = Decimal('0')

    for line in lines:
        if not isinstance(line, dict):
            raise ValueError("Each line must be a dict")

        for field in ('quantity', 'unit_price', 'vat_percent'):
            if field not in line:
                raise ValueError(f"Missing field: {field}")

        try:
            quantity = Decimal(line['quantity'])
            unit_price = Decimal(line['unit_price'])
            vat_percent = Decimal(line['vat_percent'])
        except (InvalidOperation, ValueError, ArithmeticError):
            raise ValueError("Invalid decimal value")

        if not quantity.is_finite() or not unit_price.is_finite() or not vat_percent.is_finite():
            raise ValueError("Non-finite value")

        if quantity < 0:
            raise ValueError("Negative quantity")
        if unit_price < 0:
            raise ValueError("Negative unit_price")
        if vat_percent < 0:
            raise ValueError("Negative vat_percent")

        line_net = (quantity * unit_price * (hundred - discount) / hundred).quantize(
            two_places, rounding=ROUND_HALF_UP
        )
        line_tax = (line_net * vat_percent / hundred).quantize(
            two_places, rounding=ROUND_HALF_UP
        )

        total_net += line_net
        total_tax += line_tax

    total = total_net + total_tax

    return {
        "net": str(total_net.quantize(two_places, rounding=ROUND_HALF_UP)),
        "tax": str(total_tax.quantize(two_places, rounding=ROUND_HALF_UP)),
        "total": str(total.quantize(two_places, rounding=ROUND_HALF_UP)),
    }
