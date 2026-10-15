"""Live counterfactual cache_consistency world A."""
INCLUDE_USER = False
TTL = 30

def diagnostics():
    return {"INCLUDE_USER": INCLUDE_USER, "TTL": TTL}

def run():
    cache = {}
    def query(user, now, value):
        key = user if INCLUDE_USER else 'global'
        if key in cache and now - cache[key][0] < TTL:
            return cache[key][1]
        cache[key] = (now, value)
        return value
    query('alice', 0, 'red')
    other_user = query('bob', 10, 'blue')
    refreshed_user = query('alice', 90, 'green')
    return [other_user, refreshed_user]
EXPECTED = ['blue','green']
