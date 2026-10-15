"""Live counterfactual invoice_total world B."""
CENTS_SCALE = 100
DISCOUNT_SIGN = 1

def diagnostics():
    return {"CENTS_SCALE": CENTS_SCALE, "DISCOUNT_SIGN": DISCOUNT_SIGN}

def run():
    base_dollars = 120
    discount_dollars = 20
    return (base_dollars + DISCOUNT_SIGN * discount_dollars) * CENTS_SCALE
EXPECTED = 10000
