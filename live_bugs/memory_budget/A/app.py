"""Live counterfactual memory_budget world A."""
BATCH_SIZE = 256
RETAINED_ACTIVATIONS = 0

def diagnostics():
    return {"BATCH_SIZE": BATCH_SIZE, "RETAINED_ACTIVATIONS": RETAINED_ACTIVATIONS}

def run():
    memory_mb = BATCH_SIZE * 4 + RETAINED_ACTIVATIONS * 4
    return memory_mb <= 128
EXPECTED = True
