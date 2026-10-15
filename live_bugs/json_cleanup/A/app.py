"""Live counterfactual json_cleanup world A."""
STRIP_BOM = False
STRIP_COMMA = True

def diagnostics():
    return {"STRIP_BOM": STRIP_BOM, "STRIP_COMMA": STRIP_COMMA}

import json

def run():
    payload = '\ufeff{"ok": true,}'
    if STRIP_BOM:
        payload = payload.lstrip('\ufeff')
    if STRIP_COMMA:
        payload = payload.replace(',}', '}')
    try:
        return json.loads(payload)
    except ValueError:
        return None
EXPECTED = {'ok': True}
