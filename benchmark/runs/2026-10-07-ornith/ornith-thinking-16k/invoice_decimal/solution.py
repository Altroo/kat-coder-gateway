from decimal import Decimal, ROUND_HALF_UP, InvalidOperation


def _to_decimal(value):
    try:
        d = Decimal(value)
    except (InvalidOperation, TypeError):
        raise ValueError(f"Invalid decimal value: {value!r}")
    if not d.is_finite():
        raise ValueError(f"Non-finite decimal value: {value!r}")
    return d


def _round_cents(value):
    return value.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def invoice_total(lines, discount_percent="0"):
    discount = _to_decimal(discount_percent)
    if discount < 0 or discount > 100:
        raise ValueError("discount_percent must be between 0 and 100")

    required = ("quantity", "unit_price", "vat_percent")
    total_net = Decimal("0")
    total_tax = Decimal("0")

    for line in lines:
        if not isinstance(line, dict):
            raise ValueError("Each line must be a dictionary")
        for key in required:
            if key not in line:
                raise ValueError(f"Missing field: {key}")

        quantity = _to_decimal(line["quantity"])
        unit_price = _to_decimal(line["unit_price"])
        vat_percent = _to_decimal(line["vat_percent"])

        if quantity < 0 or unit_price < 0 or vat_percent < 0:
            raise ValueError("quantities, prices and rates must be non-negative")

        net_before = quantity * unit_price
        discount_factor = Decimal("1") - (discount / Decimal("100"))
        net_rounded = _round_cents(net_before * discount_factor)

        tax_rounded = _round_cents(net_rounded * (vat_percent / Decimal("100")))

        total_net += net_rounded
        total_tax += tax_rounded

    net_total = _round_cents(total_net)
    tax_total = _round_cents(total_tax)
    total_total = _round_cents(total_net + total_tax)

    return {
        "net": str(net_total),
        "tax": str(tax_total),
        "total": str(total_total),
    }
