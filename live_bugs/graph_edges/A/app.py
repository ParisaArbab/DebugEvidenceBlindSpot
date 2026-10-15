"""Live counterfactual graph_edges world A."""
KEEP_REVERSE = False
KEEP_WRITES = True

def diagnostics():
    return {"KEEP_REVERSE": KEEP_REVERSE, "KEEP_WRITES": KEEP_WRITES}

def run():
    edges = [('a','writes','p'),('p','rev_writes','a')]
    if not KEEP_REVERSE:
        edges = [e for e in edges if e[1] != 'rev_writes']
    if not KEEP_WRITES:
        edges = [e for e in edges if e[1] != 'writes']
    return len(edges)
EXPECTED = 2
