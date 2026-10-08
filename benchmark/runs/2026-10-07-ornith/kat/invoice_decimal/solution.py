from decimal import Decimal, ROUND_HALF_UP, InvalidOperation
import math

def invoice_total(lines, discount_percent="0"):
    if not lines:
        return {"net": "0.00", "tax": "0.00", "total": "0.00"}
    
    # Validate discount_percent
    try:
        discount = Decimal(discount_percent)
    except (InvalidOperation, TypeError, ValueError):
        raise ValueError(f"Invalid discount_percent: {discount_percent}")
    
    if not discount.is_finite():
        raise ValueError("Discount percent must be finite")
    if discount < 0 or discount > 100:
        raise ValueError("Discount percent must be between 0 and 100")
    
    two_places = Decimal("0.01")
    
    total_net = Decimal("0")
    total_tax = Decimal("0")
    
    for line in lines:
        # Check for missing fields
        if "quantity" not in line or "unit_price" not in line or "vat_percent" not in line:
            raise ValueError("Missing required fields")
        
        # Parse values
        try:
            quantity = Decimal(line["quantity"])
            unit_price = Decimal(line["unit_price"])
            vat_percent = Decimal(line["vat_percent"])
        except (InvalidOperation, TypeError, ValueError):
            raise ValueError("Invalid decimal value")
        
        # Validate finiteness
        if not quantity.is_finite() or not unit_price.is_finite() or not vat_percent.is_finite():
            raise ValueError("Non-finite values not allowed")
        
        # Reject negatives
        if quantity < 0 or unit_price < 0 or vat_percent < 0:
            raise ValueError("Negative values not allowed")
        
        # Compute line net after discount
        gross = quantity * unit_price
        net = gross * (1 - discount / 100)
        net = net.quantize(two_places, rounding=ROUND_HALF_UP)
        
        # Compute tax on rounded net
        tax = net * vat_percent / 100
        tax = tax.quantize(two_places, rounding=ROUND_HALF_UP)
        
        total_net += net
        total_tax += tax
    
    total_net = total_net.quantize(two_places, rounding=ROUND_HALF_UP)
    total_tax = total_tax.quantize(two_places, rounding=ROUND_HALF_UP)
    total = (total_net + total_tax).quantize(two_places, rounding=ROUND_HALF_UP)
    
    return {
        "net": str(total_net),
        "tax": str(total_tax),
        "total": str(total)
    }
