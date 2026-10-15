"""Live counterfactual json_cleanup world B."""
STRIP_BOM = True
STRIP_COMMA = False

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
