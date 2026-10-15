"""Live counterfactual auth_window world A."""
TOKEN_TTL = 30
CLOCK_SKEW = 0

def diagnostics():
    return {"TOKEN_TTL": TOKEN_TTL, "CLOCK_SKEW": CLOCK_SKEW}

def run():
    issued_at = 10000
    request_time = 10120 + CLOCK_SKEW
    return request_time - issued_at <= TOKEN_TTL
EXPECTED = True
