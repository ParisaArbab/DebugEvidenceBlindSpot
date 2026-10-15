"""Live counterfactual stream_chunk world B."""
READ_LIMIT = 4
DROP_LAST = True

def diagnostics():
    return {"READ_LIMIT": READ_LIMIT, "DROP_LAST": DROP_LAST}

def run():
    records = [1,2,3,4]
    received = records[:READ_LIMIT]
    return received[:-1] if DROP_LAST else received
EXPECTED = [1,2,3,4]
