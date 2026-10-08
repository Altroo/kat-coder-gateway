from decimal import Decimal, ROUND_HALF_UP, InvalidOperation
import math

TWO_PLACES = Decimal("0.01")


def invoice_total(lines, discount_percent="0"):
    if not lines:
        return {"net": "0.00", "tax": "0.00", "total": "0.00"}

    try:
        discount = Decimal(str(discount_percent))
    except (InvalidOperation, ValueError, TypeError):
        raise ValueError("Invalid discount_percent")

    if not discount.is_finite() or discount < 0 or discount > 100:
        raise ValueError("Discount must be between 0 and 100")

    total_net = Decimal("0")
    total_tax = Decimal("0")

    for line in lines:
        if not isinstance(line, dict):
            raise ValueError("Each line must be a dictionary")

        if "quantity" not in line or "unit_price" not in line or "vat_percent" not in line:
            raise ValueError("Missing required field")

        try:
            quantity = Decimal(str(line["quantity"]))
            unit_price = Decimal(str(line["unit_price"]))
            vat_percent = Decimal(str(line["vat_percent"]))
        except (InvalidOperation, ValueError, TypeError):
            raise ValueError("Invalid numeric value")

        if not quantity.is_finite() or not unit_price.is_finite() or not vat_percent.is_finite():
            raise ValueError("Non-finite value encountered")

        if quantity < 0 or unit_price < 0 or vat_percent < 0:
            raise ValueError("Negative value encountered")

        raw_net = quantity * unit_price
        discounted_net = raw_net * (1 - discount / 100)
        rounded_net = discounted_net.quantize(TWO_PLACES, rounding=ROUND_HALF_UP)

        tax = (rounded_net * vat_percent / 100).quantize(TWO_PLACES, rounding=ROUND_HALF_UP)

        total_net += rounded_net
        total_tax += tax

    total = total_net + total_tax

    return {
        "net": total_net.quantize(TWO_PLACES, rounding=ROUND_HALF_UP),
        "tax": total_tax.quantize(TWO_PLACES, rounding=ROUND_HALF_UP),
        "total": total.quantize(TWO_PLACES, rounding=ROUND_HALF_UP),
    }
