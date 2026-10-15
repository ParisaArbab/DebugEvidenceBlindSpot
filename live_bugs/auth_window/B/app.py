"""Live counterfactual auth_window world B."""
TOKEN_TTL = 600
CLOCK_SKEW = 3600

def diagnostics():
    return {"TOKEN_TTL": TOKEN_TTL, "CLOCK_SKEW": CLOCK_SKEW}

def run():
    issued_at = 10000
    request_time = 10120 + CLOCK_SKEW
    return request_time - issued_at <= TOKEN_TTL
EXPECTED = True
