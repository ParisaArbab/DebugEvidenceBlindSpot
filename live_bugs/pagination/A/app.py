"""Live counterfactual pagination world A."""
MAX_PAGES = 1
ADVANCE_CURSOR = True

def diagnostics():
    return {"MAX_PAGES": MAX_PAGES, "ADVANCE_CURSOR": ADVANCE_CURSOR}

def run():
    result = []
    cursor = 0
    for _ in range(MAX_PAGES):
        result.append(cursor)
        if ADVANCE_CURSOR:
            cursor += 1
    return result
EXPECTED = [0, 1, 2, 3]
