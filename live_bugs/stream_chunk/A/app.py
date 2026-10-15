"""Live counterfactual stream_chunk world A."""
READ_LIMIT = 2
DROP_LAST = False

def diagnostics():
    return {"READ_LIMIT": READ_LIMIT, "DROP_LAST": DROP_LAST}

def run():
    records = [1,2,3,4]
    received = records[:READ_LIMIT]
    return received[:-1] if DROP_LAST else received
EXPECTED = [1,2,3,4]
