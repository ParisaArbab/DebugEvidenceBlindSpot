"""Sanitized trace captured by executing this actual buggy app."""
import sys
import app

def main():
    print('[RUN] executing test contract for the live case')
    for field, value in app.diagnostics().items():
        print(f'[DIAGNOSTIC] {field}={value!r}')
    try:
        value = app.run()
        assert value == app.EXPECTED, 'contract validation failed'
        print('[PASS] contract validation succeeded')
    except Exception:
        print('[FAIL] AssertionError: contract validation failed')
        return 1
    return 0

if __name__ == '__main__':
    sys.exit(main())
