from decimal import Decimal, ROUND_HALF_UP, InvalidOperation, getcontext


def invoice_total(lines, discount_percent="0"):
    if not isinstance(lines, list):
        raise ValueError("lines must be a list")

    try:
        discount = Decimal(discount_percent)
    except (InvalidOperation, TypeError):
        raise ValueError("Invalid discount_percent value")

    if discount < 0 or discount > 100:
        raise ValueError("Discount must be between 0 and 100")

    required_fields = ("quantity", "unit_price", "vat_percent")
    quant = Decimal("0.01")

    total_net = Decimal("0")
    total_tax = Decimal("0")

    for line in lines:
        if not isinstance(line, dict):
            raise ValueError("Each line must be a dictionary")

        for field in required_fields:
            if field not in line:
                raise ValueError(f"Missing field: {field}")

        raw_quantity = line["quantity"]
        raw_unit_price = line["unit_price"]
        raw_vat_percent = line["vat_percent"]

        try:
            quantity = Decimal(raw_quantity)
            unit_price = Decimal(raw_unit_price)
            vat_percent = Decimal(raw_vat_percent)
        except (InvalidOperation, TypeError):
            raise ValueError("Invalid decimal value in line")

        for value in (quantity, unit_price, vat_percent):
            if not value.is_finite():
                raise ValueError("Non-finite value encountered")

        if quantity < 0:
            raise ValueError("Quantity cannot be negative")
        if unit_price < 0:
            raise ValueError("Unit price cannot be negative")
        if vat_percent < 0:
            raise ValueError("VAT percent cannot be negative")

        net = quantity * unit_price
        net = net * (Decimal("1") - discount / Decimal("100"))
        net_rounded = net.quantize(quant, rounding=ROUND_HALF_UP)

        tax = net_rounded * (vat_percent / Decimal("100"))
        tax_rounded = tax.quantize(quant, rounding=ROUND_HALF_UP)

        total_net += net_rounded
        total_tax += tax_rounded

    total = total_net + total_tax

    return {
        "net": total_net.quantize(quant, rounding=ROUND_HALF_UP).format("F"),
        "tax": total_tax.quantize(quant, rounding=ROUND_HALF_UP).format("F"),
        "total": total.quantize(quant, rounding=ROUND_HALF_UP).format("F"),
    }
